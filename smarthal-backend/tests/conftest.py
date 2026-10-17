"""Shared test setup: a fake camera, a fake clock, a temporary database and one test user.

Tests never touch the real camera or data/dev.db.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402
from app import create_app  # noqa: E402
from recognition import Recognizer  # noqa: E402
from db import get_connection  # noqa: E402

TEST_PASSWORD = "correct-horse-battery"


class FakeCamera:
    """Stands in for the real camera: always online, returns a tiny fake JPEG.

    Tests set `frame` to a picture (see FakeFaceEngine) for recognition to look at.
    """
    frame = None

    def get_frame(self):
        """Return the picture a test put in front of the camera, or None."""
        return self.frame

    def is_online(self):
        """Always online."""
        return True

    def get_jpeg_frame(self):
        """Return fixed fake JPEG bytes."""
        return b"\xff\xd8fake-jpeg\xff\xd9"


class FakeFaceEngine:
    """Stands in for the face models. Test photos are solid-color images where the
    blue channel is how many faces it 'contains' and the green channel is whose face
    it is, so tests can make no-face, two-face and different-person photos."""
    model = "fake-engine"
    consistency_threshold = 0.5
    match_threshold = 0.5

    def detect_faces(self, img):
        """Return (box, embedding) per 'face'; the same person always gets the same embedding."""
        count, person = int(img[0, 0, 0]), int(img[0, 0, 1])
        emb = np.zeros(8, np.float32)
        emb[person % 8] = 1.0
        return [((10.0 * i, 5.0, 8.0, 8.0), emb) for i in range(count)]

    def embed_faces(self, img):
        """Return one embedding per 'face'."""
        return [emb for _, emb in self.detect_faces(img)]


class FakeClock:
    """A clock tests can move forward instantly, to test timeouts without waiting."""
    def __init__(self):
        """Start at an arbitrary fixed time."""
        self.now = 1000.0

    def __call__(self):
        """Return the current fake time."""
        return self.now

    def advance(self, seconds):
        """Move the clock forward by this many seconds."""
        self.now += seconds


@pytest.fixture
def clock():
    """A fresh fake clock for each test."""
    return FakeClock()


@pytest.fixture
def sessions(clock):
    """A session store that uses the fake clock."""
    return auth.SessionStore(clock=clock)


@pytest.fixture
def camera():
    """The fake camera the app reads from; tests can set camera.frame."""
    return FakeCamera()


@pytest.fixture
def app(tmp_path, monkeypatch, clock, sessions, camera):
    """The Flask app on a temporary database, with one user: alex / TEST_PASSWORD."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("RESIDENT_PHOTOS_DIR", str(tmp_path / "residents"))
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("RECOGNITION_THRESHOLD", raising=False)
    engine = FakeFaceEngine()
    app = create_app(camera, sessions=sessions,
                     login_limiter=auth.LoginRateLimiter(clock=clock),
                     face_engine=engine,
                     recognizer=Recognizer(camera, engine, background=False, clock=clock))
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("alex", auth.hash_password(TEST_PASSWORD), "home_user"),
    )
    conn.commit()
    conn.close()
    return app


@pytest.fixture
def client(app):
    """A test client for sending requests to the app."""
    return app.test_client()


@pytest.fixture
def token(client):
    """Log in as alex and return the session token."""
    resp = client.post("/login", json={"username": "alex", "password": TEST_PASSWORD})
    assert resp.status_code == 200
    return resp.get_json()["token"]


def bearer(token):
    """Return the Authorization header for a token."""
    return {"Authorization": f"Bearer {token}"}
