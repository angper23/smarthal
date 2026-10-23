"""SmartHal Flask backend: login, sessions, the live camera stream, resident registration and recognition.

Run with `python app.py` (serves on 127.0.0.1:5001). Endpoints are listed in the project README.md (section 6).
"""

import logging
import os
import re
import shutil
import sqlite3
import threading
import time

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS

import auth
import faces
from liveness import LivenessChecker
from recognition import Recognizer
from db import BACKEND_DIR, get_connection, init_db

load_dotenv()

# The frontend only samples 5 frames/sec for face detection, so there's no
# benefit to encoding and sending full camera framerate (the Reolink's 4K
# main stream) — doing so wastes CPU re-encoding frames nobody looks at,
# which was making the reader thread more likely to fall behind and stall
# after a reconnect. Capping output here costs nothing visually and reduces
# that contention.
MJPEG_TARGET_FPS = 10
MJPEG_FRAME_INTERVAL = 1 / MJPEG_TARGET_FPS

# How often an open stream re-checks that the session it was opened under
# still exists, so logging out (or idling out) cuts off the video.
STREAM_SESSION_CHECK_SECONDS = 5

INVALID_LOGIN = {"error": "Invalid username or password"}

# Same rule as seed_user.py.
MIN_PASSWORD_LENGTH = 8

# Register Resident: the webcam capture takes one photo per angle, in this order.
RESIDENT_ANGLES = ("front", "left", "right", "up", "down")
MAX_RESIDENT_NAME = 100
MAX_PHOTO_BYTES = 5 * 1024 * 1024
# Whole request: five photos plus the form fields. Bigger requests get 413.
MAX_REQUEST_BYTES = len(RESIDENT_ANGLES) * MAX_PHOTO_BYTES + 1024 * 1024


class _RedactTokensFilter(logging.Filter):
    """The dev server logs every request line, query string included, which
    would print each stream_token. Mask it before it reaches the log."""

    _pattern = re.compile(r"(stream_token=)[^&\s\"]+")

    def filter(self, record):
        """Rewrite the log line so any stream_token value shows as [redacted]."""
        record.msg = self._pattern.sub(r"\1[redacted]", str(record.msg))
        if record.args:
            record.args = tuple(
                self._pattern.sub(r"\1[redacted]", a) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def cors_origins():
    """Return the frontend origins allowed to call the API (from CORS_ORIGINS).

    Defaults to http://localhost:5173. Refuses '*', which would let any site read the stream.
    """
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        # A wildcard would let any website read the camera stream and the
        # API responses for a logged-in user. Refuse rather than allow it.
        raise RuntimeError("CORS_ORIGINS must list specific origins, not '*'.")
    return origins


def resident_photos_dir():
    """Folder for registered residents' photos (RESIDENT_PHOTOS_DIR, default data/residents/).

    Under data/, which is gitignored: these are photos of real people's faces.
    """
    path = os.environ.get("RESIDENT_PHOTOS_DIR", "data/residents")
    return path if os.path.isabs(path) else os.path.join(BACKEND_DIR, path)


def create_app(camera, sessions=None, login_limiter=None, password_limiter=None, face_engine=None,
               recognizer=None):
    """Build and return the Flask app.

    camera: anything with is_online() and get_jpeg_frame() (the real Camera, or a fake in tests).
    sessions, login_limiter, password_limiter: optional, so tests can pass in versions with a fake clock.
    face_engine: anything with embed_faces(img), detect_faces(img), model, consistency_threshold
        and match_threshold (default: faces.LazyEngine, which loads the real models on first use;
        tests pass a fake).
    recognizer: Live Feed recognition (default: a background recognition.Recognizer on this
        camera and engine, with liveness checking unless LIVENESS_CHECK=off; tests pass one
        with background=False).
    """
    sessions = sessions or auth.SessionStore()
    login_limiter = login_limiter or auth.LoginRateLimiter()
    # Wrong "current password" attempts on /change-password, limited like
    # logins so a hijacked session can't be used to guess the password.
    password_limiter = password_limiter or auth.LoginRateLimiter()
    face_engine = face_engine or faces.LazyEngine()
    # Liveness is on unless LIVENESS_CHECK=off in .env (e.g. to test recognition alone)
    liveness_on = os.environ.get("LIVENESS_CHECK", "on").lower() not in ("off", "0", "false", "no")
    recognizer = recognizer or Recognizer(camera, face_engine, liveness=LivenessChecker() if liveness_on else None)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    app.extensions["sessions"] = sessions
    app.extensions["face_engine"] = face_engine
    app.extensions["recognizer"] = recognizer
    # Only the frontend's own origin(s) may read responses — the stream and
    # API are behind auth now, but there's still no reason to let other
    # sites try. Retry-After is exposed so the login screen could read it.
    CORS(
        app,
        origins=cors_origins(),
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After"],
    )
    werkzeug_logger = logging.getLogger("werkzeug")
    if not any(isinstance(f, _RedactTokensFilter) for f in werkzeug_logger.filters):
        werkzeug_logger.addFilter(_RedactTokensFilter())

    init_db()

    def mjpeg_generator(session_token):
        """Yield camera frames as an MJPEG stream (about 10 per second).

        Every few seconds it re-checks the session, so logging out or timing out stops the video.
        """
        next_session_check = time.monotonic() + STREAM_SESSION_CHECK_SECONDS
        while True:
            tick_start = time.time()

            if time.monotonic() >= next_session_check:
                if not sessions.is_active(session_token):
                    return
                next_session_check = time.monotonic() + STREAM_SESSION_CHECK_SECONDS

            frame = camera.get_jpeg_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )

            elapsed = time.time() - tick_start
            remaining = MJPEG_FRAME_INTERVAL - elapsed
            if remaining > 0:
                time.sleep(remaining)

    @app.route("/login", methods=["POST"])
    def login():
        """POST /login: check username + password and start a session.

        Returns {token, expires_in, user}. Unknown user and wrong password get the same 401;
        5 failures for one username + IP in 15 minutes gives 429.
        """
        body = request.get_json(silent=True) or {}
        username = body.get("username")
        password = body.get("password")
        if not isinstance(username, str) or not isinstance(password, str) \
                or not username.strip() or not password:
            return jsonify(INVALID_LOGIN), 401
        username = username.strip()

        # Keyed on username + IP so one person mistyping can't lock out
        # everyone else, and one IP can't grind through a single account.
        limiter_key = (username.lower(), request.remote_addr)
        retry_after = login_limiter.retry_after(limiter_key)
        if retry_after:
            resp = jsonify({"error": "Too many attempts. Try again later."})
            resp.headers["Retry-After"] = str(retry_after)
            return resp, 429

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        finally:
            conn.close()

        # verify_password runs bcrypt even when row is None, so unknown
        # usernames and wrong passwords take the same time and get the
        # same response.
        if not auth.verify_password(password, row["password_hash"] if row else None):
            login_limiter.record_failure(limiter_key)
            return jsonify(INVALID_LOGIN), 401

        login_limiter.reset(limiter_key)
        user = {"id": row["id"], "username": row["username"], "role": row["role"]}
        token = sessions.create(user)
        return jsonify({
            "token": token,
            "expires_in": auth.SESSION_IDLE_SECONDS,
            "user": user,
        })

    @app.route("/logout", methods=["POST"])
    @auth.require_auth
    def logout():
        """POST /logout: end the current session (any video opened with it stops too)."""
        sessions.revoke(g.session_token)
        return "", 204

    @app.route("/me")
    @auth.require_auth
    def me():
        """GET /me: return the logged-in user. The frontend uses it to check a saved token is still valid."""
        return jsonify({"user": g.user})

    @app.route("/change-password", methods=["POST"])
    @auth.require_auth
    def change_password():
        """POST /change-password: change the logged-in user's password.

        Requires the current password. On success, signs out the account's other sessions
        (this one stays logged in).
        """
        limiter_key = (g.user["id"], request.remote_addr)
        retry_after = password_limiter.retry_after(limiter_key)
        if retry_after:
            resp = jsonify({"error": "Too many attempts. Try again later."})
            resp.headers["Retry-After"] = str(retry_after)
            return resp, 429

        body = request.get_json(silent=True) or {}
        current = body.get("current_password")
        new = body.get("new_password")
        if not isinstance(current, str) or not isinstance(new, str):
            return jsonify({"error": "Current and new password are required"}), 400

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (g.user["id"],)
            ).fetchone()
            # Re-checking the current password means someone who only has a
            # logged-in session (e.g. an unattended laptop) can't take over
            # the account. 403, not 401: a 401 would log the user out.
            if not auth.verify_password(current, row["password_hash"] if row else None):
                password_limiter.record_failure(limiter_key)
                return jsonify({"error": "Current password is incorrect"}), 403
            password_limiter.reset(limiter_key)

            if len(new) < MIN_PASSWORD_LENGTH:
                return jsonify({"error": f"New password must be at least {MIN_PASSWORD_LENGTH} characters"}), 400
            if len(new.encode("utf-8")) > auth.MAX_PASSWORD_BYTES:
                return jsonify({"error": f"New password must be at most {auth.MAX_PASSWORD_BYTES} bytes"}), 400
            if new == current:
                return jsonify({"error": "New password must be different from the current one"}), 400

            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (auth.hash_password(new), g.user["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        sessions.revoke_other_sessions(g.user["id"], keep_token=g.session_token)
        return "", 204

    @app.route("/stream-token", methods=["POST"])
    @auth.require_auth
    def stream_token():
        """POST /stream-token: issue a 60-second token for opening /video_feed.

        Needed because an <img> tag can't send the Authorization header.
        """
        return jsonify({
            "stream_token": sessions.create_stream_token(g.session_token),
            "expires_in": auth.STREAM_TOKEN_SECONDS,
        })

    @app.route("/video_feed")
    def video_feed():
        """GET /video_feed?stream_token=...: the live MJPEG camera stream."""
        session_token = sessions.redeem_stream_token(request.args.get("stream_token", ""))
        if session_token is None:
            return jsonify({"error": "Authentication required"}), 401
        return Response(
            mjpeg_generator(session_token),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    @app.route("/status")
    @auth.require_auth
    def status():
        """GET /status: report whether the backend is currently receiving camera frames."""
        return jsonify({"camera_online": camera.is_online()})

    @app.route("/recognitions")
    @auth.require_auth
    def recognitions():
        """GET /recognitions: who's in front of the camera right now.

        Returns {faces: [{box, status, resident_id, name, score, liveness}], age_seconds,
        threshold, error}. box is [x, y, width, height] as fractions of the frame. status is
        resident, unknown, checking, spoof, too_far or unverified; name is only set for
        resident (a match that also passed the liveness check). Live Feed polls this a few times a second; recognition pauses when nobody does.
        """
        result = recognizer.latest()
        result["camera_online"] = camera.is_online()
        return jsonify(result)

    @app.errorhandler(413)
    def too_large(_err):
        """Return JSON (not Flask's HTML page) when an upload is over MAX_REQUEST_BYTES."""
        return jsonify({"error": "Photos are too large. Each must be under 5 MB."}), 413

    def photo_error(angle, reason, message):
        """400 response pointing at one capture angle, so the screen can ask for a retake of just that one."""
        return jsonify({"error": message, "angle": angle, "reason": reason}), 400

    @app.route("/residents", methods=["POST"])
    @auth.require_auth
    def register_resident():
        """POST /residents (multipart): register a resident from one webcam photo per angle.

        Form fields: name, plus one image file per angle in RESIDENT_ANGLES.
        Each photo must contain exactly one face, and every angle must look like the
        same person as the front photo. Returns 201 {resident: {id, name, angles}};
        a bad photo gives 400 {error, angle, reason} (reason: invalid_image, no_face,
        multiple_faces or different_person).
        """
        name = (request.form.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Resident name is required"}), 400
        if len(name) > MAX_RESIDENT_NAME:
            return jsonify({"error": f"Resident name must be at most {MAX_RESIDENT_NAME} characters"}), 400

        images = {}
        for angle in RESIDENT_ANGLES:
            upload = request.files.get(angle)
            if upload is None:
                return photo_error(angle, "missing", f"The {angle} photo is missing.")
            data = upload.read(MAX_PHOTO_BYTES + 1)
            if len(data) > MAX_PHOTO_BYTES:
                return photo_error(angle, "too_large", f"The {angle} photo is over 5 MB.")
            # Decoding is the real type check; the browser-supplied filename
            # and content type can say anything.
            img = faces.decode_image(data)
            if img is None:
                return photo_error(angle, "invalid_image", f"The {angle} photo isn't a readable image.")
            images[angle] = img

        embeddings = {}
        for angle in RESIDENT_ANGLES:
            found = face_engine.embed_faces(images[angle])
            if not found:
                return photo_error(angle, "no_face",
                                   f"No face found in the {angle} photo. Retake it in good light, close to the camera.")
            if len(found) > 1:
                return photo_error(angle, "multiple_faces",
                                   f"More than one face in the {angle} photo. Only the resident should be in frame.")
            embeddings[angle] = np.asarray(found[0], dtype=np.float32)

        # Catches someone else stepping in partway through the capture.
        for angle in RESIDENT_ANGLES[1:]:
            if faces.cosine(embeddings["front"], embeddings[angle]) < face_engine.consistency_threshold:
                return photo_error(angle, "different_person",
                                   f"The {angle} photo doesn't look like the same person as the front photo. Retake it.")

        conn = get_connection()
        folder = None
        try:
            resident_id = conn.execute(
                "INSERT INTO residents (registered_by, name) VALUES (?, ?)",
                (g.user["id"], name),
            ).lastrowid
            folder = os.path.join(resident_photos_dir(), str(resident_id))
            os.makedirs(folder, mode=0o700, exist_ok=True)
            for angle in RESIDENT_ANGLES:
                rel_path = f"{resident_id}/{angle}.jpg"
                # Saved from the decoded pixels, not the uploaded bytes: drops
                # any metadata (e.g. location) and anything that isn't an image.
                if not cv2.imwrite(os.path.join(folder, f"{angle}.jpg"), images[angle],
                                   [cv2.IMWRITE_JPEG_QUALITY, 90]):
                    raise OSError(f"could not save the {angle} photo")
                conn.execute(
                    "INSERT INTO resident_face_angles (resident_id, angle, embedding, model, photo_path)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (resident_id, angle, embeddings[angle].tobytes(), face_engine.model, rel_path),
                )
            conn.execute("UPDATE residents SET photo_path = ? WHERE id = ?",
                         (f"{resident_id}/front.jpg", resident_id))
            conn.commit()
        except Exception:
            conn.rollback()
            if folder:
                shutil.rmtree(folder, ignore_errors=True)
            raise
        finally:
            conn.close()

        recognizer.invalidate()  # Live Feed should recognize them right away
        return jsonify({"resident": {"id": resident_id, "name": name, "angles": list(RESIDENT_ANGLES)}}), 201

    @app.route("/residents", methods=["GET"])
    @auth.require_auth
    def list_residents():
        """GET /residents: every registered resident, newest first, with who registered them."""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT r.id, r.name, r.registered_by, u.username AS registered_by_name,"
                " (SELECT COUNT(*) FROM resident_face_angles a WHERE a.resident_id = r.id) AS angles"
                " FROM residents r JOIN users u ON u.id = r.registered_by ORDER BY r.id DESC"
            ).fetchall()
        finally:
            conn.close()
        user = g.user
        return jsonify({"residents": [
            {
                "id": r["id"],
                "name": r["name"],
                "registered_by": r["registered_by_name"],
                "angles": r["angles"],
                "can_delete": user["role"] == "admin" or r["registered_by"] == user["id"],
            }
            for r in rows
        ]})

    @app.route("/residents/<int:resident_id>", methods=["DELETE"])
    @auth.require_auth
    def delete_resident(resident_id):
        """DELETE /residents/<id>: remove a resident, their face embeddings and their photos.

        Allowed for the user who registered them, or an admin. 204 on success, 404 if there's
        no such resident, 403 if not allowed, 409 if detection events still point at them.
        """
        conn = get_connection()
        try:
            row = conn.execute("SELECT registered_by FROM residents WHERE id = ?", (resident_id,)).fetchone()
            if row is None:
                return jsonify({"error": "Resident not found"}), 404
            if g.user["role"] != "admin" and row["registered_by"] != g.user["id"]:
                return jsonify({"error": "Only the person who registered this resident, or an admin, can delete them"}), 403
            try:
                # resident_face_angles rows go with it (ON DELETE CASCADE)
                conn.execute("DELETE FROM residents WHERE id = ?", (resident_id,))
                conn.commit()
            except sqlite3.IntegrityError:
                # Detection events (a later sprint) reference residents; don't silently rewrite history
                return jsonify({"error": "This resident appears in recorded events and can't be deleted yet"}), 409
        finally:
            conn.close()

        # Photos last: if the database delete failed above, nothing was removed
        shutil.rmtree(os.path.join(resident_photos_dir(), str(resident_id)), ignore_errors=True)
        recognizer.invalidate()
        return "", 204

    return app


if __name__ == "__main__":
    from camera import Camera

    rtsp_url = os.environ.get("RTSP_URL")
    if not rtsp_url:
        raise RuntimeError(
            "RTSP_URL is not set. Copy .env.example to .env and fill in your "
            "camera's RTSP URL."
        )

    face_engine = faces.LazyEngine()

    def warm_up_faces():
        """Load the face models in the background so the first registration isn't slow."""
        try:
            face_engine.warm_up()
        except Exception:
            logging.exception("Couldn't load the face models; Register Resident will retry on first use")

    threading.Thread(target=warm_up_faces, daemon=True).start()
    app = create_app(Camera(rtsp_url), face_engine=face_engine)
    # 127.0.0.1, not 0.0.0.0: even with login in place, there's no reason
    # for anyone else on the same WiFi/LAN to reach this server directly.
    # The frontend runs on this same machine, and remote access will go
    # through a tunnel, which also connects from localhost.
    app.run(host="127.0.0.1", port=5001, threaded=True)
