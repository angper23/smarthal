"""SmartHal Flask backend: login, sessions, and the live camera stream.

Run with `python app.py` (serves on 127.0.0.1:5001). Endpoints are listed in the project README.md (section 6).
"""

import logging
import os
import re
import time

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS

import auth
from db import get_connection, init_db

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


def create_app(camera, sessions=None, login_limiter=None, password_limiter=None):
    """Build and return the Flask app.

    camera: anything with is_online() and get_jpeg_frame() (the real Camera, or a fake in tests).
    sessions, login_limiter, password_limiter: optional, so tests can pass in versions with a fake clock.
    """
    sessions = sessions or auth.SessionStore()
    login_limiter = login_limiter or auth.LoginRateLimiter()
    # Wrong "current password" attempts on /change-password, limited like
    # logins so a hijacked session can't be used to guess the password.
    password_limiter = password_limiter or auth.LoginRateLimiter()

    app = Flask(__name__)
    app.extensions["sessions"] = sessions
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

    return app


if __name__ == "__main__":
    from camera import Camera

    rtsp_url = os.environ.get("RTSP_URL")
    if not rtsp_url:
        raise RuntimeError(
            "RTSP_URL is not set. Copy .env.example to .env and fill in your "
            "camera's RTSP URL."
        )

    app = create_app(Camera(rtsp_url))
    # 127.0.0.1, not 0.0.0.0: even with login in place, there's no reason
    # for anyone else on the same WiFi/LAN to reach this server directly.
    # The frontend runs on this same machine, and remote access will go
    # through a tunnel, which also connects from localhost.
    app.run(host="127.0.0.1", port=5001, threaded=True)
