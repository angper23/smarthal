"""Live Feed face recognition: who is in front of the camera right now.

A background thread takes the newest camera frame a few times a second, finds
the faces in it, and compares each one against every saved angle of every
registered resident (resident_face_angles). The best match above the
threshold gives the resident's name; anything else is "Unknown".

Frames are only analyzed in memory: nothing is saved. The thread only works
while someone has Live Feed open (it pauses when nobody has asked for results
recently), so an unwatched camera costs no CPU.
"""
import os
import threading
import time

import cv2
import numpy as np

from db import get_connection

# Frames are shrunk to this many pixels on the long side before detection.
# The Reolink's main stream is 4K; detectors don't need that, and a smaller
# frame keeps each pass around a third of a second on an M2.
MAX_SIDE = 1280

# Aim for a new result about this often while someone is watching.
INTERVAL_SECONDS = 0.3

# Stop working if nobody has asked for results for this long.
IDLE_AFTER_SECONDS = 10


class ResidentGallery:
    """Every saved face angle of every resident, as one matrix for fast matching.

    Only embeddings from the current face library (`model`) are used: embeddings
    from different libraries can't be compared.
    """

    def __init__(self, model):
        """model: the face engine's model name, e.g. 'insightface-buffalo_l'."""
        self.model = model
        self.embeddings = np.zeros((0, 0), np.float32)  # one row per saved angle
        self.owners = []                                 # resident id for each row
        self.names = {}                                  # resident id -> name

    def load(self):
        """Read the residents and their angle embeddings from the database."""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT a.resident_id, r.name, a.embedding FROM resident_face_angles a"
                " JOIN residents r ON r.id = a.resident_id WHERE a.model = ?",
                (self.model,),
            ).fetchall()
        finally:
            conn.close()
        vectors = [np.frombuffer(r["embedding"], np.float32) for r in rows]
        if vectors:
            m = np.vstack(vectors)
            self.embeddings = m / np.linalg.norm(m, axis=1, keepdims=True)
        else:
            self.embeddings = np.zeros((0, 0), np.float32)
        self.owners = [r["resident_id"] for r in rows]
        self.names = {r["resident_id"]: r["name"] for r in rows}

    def best_match(self, embedding):
        """Return (resident_id, score) for the most similar resident, or (None, 0.0) if none saved.

        Each resident's score is their best angle, so someone seen from the side
        matches their saved side angle rather than their front photo.
        """
        if not self.owners:
            return None, 0.0
        emb = embedding / np.linalg.norm(embedding)
        scores = self.embeddings @ emb
        best = {}
        for owner, score in zip(self.owners, scores):
            if score > best.get(owner, -1.0):
                best[owner] = float(score)
        resident_id = max(best, key=best.get)
        return resident_id, best[resident_id]


class Recognizer:
    """Runs recognition on the live camera and keeps the latest result.

    background=False runs one pass per request instead of a thread (used by tests).
    """

    def __init__(self, camera, engine, threshold=None, background=True, clock=time.monotonic):
        """camera: has get_frame(). engine: has detect_faces(img), model and match_threshold."""
        self.camera = camera
        self.engine = engine
        env = os.environ.get("RECOGNITION_THRESHOLD")
        self.threshold = threshold if threshold is not None else (float(env) if env else engine.match_threshold)
        self.background = background
        self._clock = clock
        self._lock = threading.Lock()
        self._gallery = None            # loaded on first use
        self._gallery_stale = True
        self._result = {"faces": [], "updated": None, "error": None}
        self._last_request = 0.0
        self._thread = None

    def invalidate(self):
        """Reload the residents before the next pass (call after registering or deleting one)."""
        with self._lock:
            self._gallery_stale = True

    def latest(self):
        """Return the newest result, and keep (or start) the background work going."""
        with self._lock:
            self._last_request = self._clock()
            start = self.background and (self._thread is None or not self._thread.is_alive())
            if start:
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()
        if not self.background:
            self.run_once()
        with self._lock:
            result = dict(self._result)
        updated = result.pop("updated")
        result["age_seconds"] = None if updated is None else round(self._clock() - updated, 2)
        result["threshold"] = self.threshold
        return result

    def run_once(self):
        """Analyze the newest camera frame once and store the result."""
        frame = self.camera.get_frame()
        try:
            faces = [] if frame is None else self.recognize(frame)
            error = None
        except Exception as exc:  # e.g. models failed to load; keep the thread alive
            faces, error = [], f"Recognition unavailable: {type(exc).__name__}"
        with self._lock:
            self._result = {"faces": faces, "updated": self._clock(), "error": error}

    def recognize(self, frame):
        """Return one entry per face in the frame: box (fractions of the frame), name or None, score."""
        h, w = frame.shape[:2]
        scale = min(1.0, MAX_SIDE / max(h, w))
        img = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else frame
        ih, iw = img.shape[:2]

        gallery = self._current_gallery()
        out = []
        for (x, y, bw, bh), emb in self.engine.detect_faces(img):
            # Keep the box inside the frame (a face filling the view can overhang the edges)
            x0, y0 = max(0.0, x), max(0.0, y)
            bw, bh = min(iw, x + bw) - x0, min(ih, y + bh) - y0
            x, y = x0, y0
            resident_id, score = gallery.best_match(emb)
            known = resident_id is not None and score >= self.threshold
            out.append({
                # As fractions of the frame, so the browser can scale them to any display size
                "box": [round(x / iw, 4), round(y / ih, 4), round(bw / iw, 4), round(bh / ih, 4)],
                "resident_id": resident_id if known else None,
                "name": gallery.names[resident_id] if known else None,
                "score": round(score, 3),
            })
        return out

    def _current_gallery(self):
        """Return the resident gallery, reloading it from the database if it changed."""
        with self._lock:
            reload = self._gallery_stale or self._gallery is None
            self._gallery_stale = False
        if reload:
            gallery = ResidentGallery(self.engine.model)
            gallery.load()
            with self._lock:
                self._gallery = gallery
        return self._gallery

    def _loop(self):
        """Background thread: recognize while someone is watching, then stop."""
        while True:
            with self._lock:
                idle = self._clock() - self._last_request > IDLE_AFTER_SECONDS
            if idle:
                with self._lock:
                    self._result = {"faces": [], "updated": None, "error": None}
                return  # latest() starts a new thread when someone opens Live Feed again
            started = time.monotonic()
            self.run_once()
            time.sleep(max(0.05, INTERVAL_SECONDS - (time.monotonic() - started)))
