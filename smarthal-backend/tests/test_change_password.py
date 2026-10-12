"""Tests for POST /change-password."""

from conftest import TEST_PASSWORD, bearer
from db import get_connection

NEW_PASSWORD = "brand-new-password-9"


def change(client, token, current=TEST_PASSWORD, new=NEW_PASSWORD):
    """Send POST /change-password for this token's user and return the response."""
    return client.post("/change-password", headers=bearer(token),
                       json={"current_password": current, "new_password": new})


def login(client, password):
    """Try logging in as alex with this password."""
    return client.post("/login", json={"username": "alex", "password": password})


def test_change_password_works(client, token):
    """After a change, only the new password logs in."""
    assert change(client, token).status_code == 204
    assert login(client, TEST_PASSWORD).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200


def test_new_password_is_stored_as_bcrypt_hash(client, token):
    """The new password is saved as a bcrypt hash."""
    change(client, token)
    conn = get_connection()
    h = conn.execute("SELECT password_hash FROM users WHERE username='alex'").fetchone()[0]
    conn.close()
    assert h.startswith("$2b$") and NEW_PASSWORD not in h


def test_requires_login(client):
    """Changing a password needs a logged-in session."""
    resp = client.post("/change-password",
                       json={"current_password": TEST_PASSWORD, "new_password": NEW_PASSWORD})
    assert resp.status_code == 401


def test_wrong_current_password_is_refused_without_logging_out(client, token):
    """A wrong current password is refused (403) and the user stays logged in."""
    resp = change(client, token, current="not-my-password")
    # 403, not 401 — the frontend treats 401 as "session gone" and logs out.
    assert resp.status_code == 403
    assert login(client, TEST_PASSWORD).status_code == 200
    assert client.get("/me", headers=bearer(token)).status_code == 200


def test_new_password_rules(client, token):
    """Too short, too long, unchanged and missing passwords are rejected."""
    assert change(client, token, new="short").status_code == 400
    assert change(client, token, new="x" * 73).status_code == 400
    assert change(client, token, new=TEST_PASSWORD).status_code == 400
    assert client.post("/change-password", headers=bearer(token), json={}).status_code == 400
    # Nothing changed.
    assert login(client, TEST_PASSWORD).status_code == 200


def test_wrong_current_password_is_rate_limited(client, token):
    """5 wrong current passwords lock the form for 15 minutes."""
    for _ in range(5):
        assert change(client, token, current="guess").status_code == 403
    resp = change(client, token)  # even the right one, while locked
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_other_sessions_are_signed_out_but_current_stays(client, token):
    """Other devices are signed out; the device that made the change stays logged in."""
    other_device = login(client, TEST_PASSWORD).get_json()["token"]
    assert change(client, token).status_code == 204
    assert client.get("/me", headers=bearer(other_device)).status_code == 401
    assert client.get("/me", headers=bearer(token)).status_code == 200


def test_other_sessions_open_stream_ends(client, token, monkeypatch):
    """Another device's open video stream stops after a password change."""
    import app as app_module
    monkeypatch.setattr(app_module, "STREAM_SESSION_CHECK_SECONDS", 0)
    other_device = login(client, TEST_PASSWORD).get_json()["token"]
    st = client.post("/stream-token", headers=bearer(other_device)).get_json()["stream_token"]
    resp = client.get(f"/video_feed?stream_token={st}", buffered=False)
    chunks = iter(resp.response)
    next(chunks)
    change(client, token)
    assert list(chunks) == []
