"""Shared test setup: a fake camera, a fake clock, a temporary database and one test user.

Tests never touch the real camera or data/dev.db.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth  # noqa: E402
from app import create_app  # noqa: E402
from db import get_connection  # noqa: E402

TEST_PASSWORD = "correct-horse-battery"


class FakeCamera:
    """Stands in for the real camera: always online, returns a tiny fake JPEG."""
    def is_online(self):
        """Always online."""
        return True

    def get_jpeg_frame(self):
        """Return fixed fake JPEG bytes."""
        return b"\xff\xd8fake-jpeg\xff\xd9"


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
def app(tmp_path, monkeypatch, clock, sessions):
    """The Flask app on a temporary database, with one user: alex / TEST_PASSWORD."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    app = create_app(FakeCamera(), sessions=sessions,
                     login_limiter=auth.LoginRateLimiter(clock=clock))
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
