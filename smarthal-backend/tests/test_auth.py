"""Tests for login, sessions, rate limiting and the protected camera routes."""

import time

import auth
from conftest import TEST_PASSWORD, bearer
from db import get_connection


def login(client, username="alex", password=TEST_PASSWORD):
    """Send POST /login and return the response."""
    return client.post("/login", json={"username": username, "password": password})


# --- login ---------------------------------------------------------------

def test_valid_login_returns_token_and_user(client):
    """Correct credentials return a token, a 30-minute expiry and the user."""
    resp = login(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["token"]) >= 40
    assert body["expires_in"] == 1800
    assert body["user"] == {"id": 1, "username": "alex", "role": "home_user"}


def test_wrong_password_is_401_with_generic_error(client):
    """A wrong password gets 401 and the generic message."""
    resp = login(client, password="wrong-password")
    assert resp.status_code == 401
    assert resp.get_json() == {"error": "Invalid username or password"}


def test_unknown_user_gets_same_response_as_wrong_password(client):
    """An unknown username looks exactly like a wrong password."""
    wrong_pw = login(client, password="wrong-password")
    unknown = login(client, username="nobody", password="wrong-password")
    assert unknown.status_code == 401
    assert unknown.get_json() == wrong_pw.get_json()


def test_unknown_user_still_runs_bcrypt(client, monkeypatch):
    """bcrypt still runs for unknown users, so timing can't reveal real usernames."""
    calls = []
    real_checkpw = auth.bcrypt.checkpw
    monkeypatch.setattr(auth.bcrypt, "checkpw",
                        lambda pw, h: calls.append(h) or real_checkpw(pw, h))
    login(client, username="nobody", password="whatever")
    assert len(calls) == 1


def test_unknown_user_timing_is_similar(client):
    """Unknown-user and wrong-password logins take similar time."""
    def timed(**kw):
        """Return how long one login request takes."""
        start = time.perf_counter()
        login(client, **kw)
        return time.perf_counter() - start

    wrong_pw = min(timed(password="nope-nope") for _ in range(3))
    unknown = min(timed(username=f"ghost{i}", password="nope-nope") for i in range(3))
    # Both are dominated by one bcrypt check; a skipped check would be ~100x faster.
    assert unknown > wrong_pw * 0.5


def test_missing_fields_are_401(client):
    """Empty or non-JSON login requests are rejected."""
    assert client.post("/login", json={}).status_code == 401
    assert client.post("/login", data="not json").status_code == 401


def test_password_hash_is_bcrypt(client):
    """Stored passwords are bcrypt hashes, never plaintext."""
    conn = get_connection()
    row = conn.execute("SELECT password_hash FROM users WHERE username = 'alex'").fetchone()
    conn.close()
    assert row["password_hash"].startswith("$2b$")
    assert TEST_PASSWORD not in row["password_hash"]


# --- rate limit ----------------------------------------------------------

def test_sixth_failure_in_window_is_429(client, clock):
    """5 failures lock that username + IP; other usernames aren't affected."""
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    resp = login(client, password="wrong")
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0
    # Even the right password is refused while locked out.
    assert login(client).status_code == 429
    # A different username from the same IP isn't affected.
    assert login(client, username="someone-else", password="wrong").status_code == 401


def test_rate_limit_window_expires(client, clock):
    """The lockout lifts after 15 minutes."""
    for _ in range(5):
        login(client, password="wrong")
    assert login(client).status_code == 429
    clock.advance(15 * 60 + 1)
    assert login(client).status_code == 200


# --- protected routes ----------------------------------------------------

def test_status_without_token_is_401(client):
    """/status refuses missing or made-up tokens."""
    assert client.get("/status").status_code == 401
    assert client.get("/status", headers=bearer("made-up")).status_code == 401


def test_status_with_token(client, token):
    """/status works with a valid token."""
    resp = client.get("/status", headers=bearer(token))
    assert resp.status_code == 200
    assert resp.get_json() == {"camera_online": True}


def test_me_returns_current_user(client, token):
    """/me returns who is logged in."""
    resp = client.get("/me", headers=bearer(token))
    assert resp.get_json()["user"]["username"] == "alex"


def test_session_expires_after_30_idle_minutes(client, token, clock):
    """Activity keeps a session alive; 30 idle minutes ends it."""
    clock.advance(29 * 60)
    assert client.get("/me", headers=bearer(token)).status_code == 200
    # That request reset the idle timer.
    clock.advance(29 * 60)
    assert client.get("/me", headers=bearer(token)).status_code == 200
    clock.advance(30 * 60 + 1)
    assert client.get("/me", headers=bearer(token)).status_code == 401


def test_logout_revokes_token(client, token):
    """After logout the old token stops working."""
    assert client.post("/logout", headers=bearer(token)).status_code == 204
    assert client.get("/status", headers=bearer(token)).status_code == 401


# --- video feed ----------------------------------------------------------

def get_stream_token(client, token):
    """Get a stream token for this session and check it lasts 60 seconds."""
    resp = client.post("/stream-token", headers=bearer(token))
    assert resp.status_code == 200
    assert resp.get_json()["expires_in"] == 60
    return resp.get_json()["stream_token"]


def test_video_feed_without_or_with_bad_stream_token_is_401(client, token):
    """/video_feed needs a real stream token; a session token isn't accepted."""
    assert client.get("/video_feed").status_code == 401
    assert client.get("/video_feed?stream_token=bogus").status_code == 401
    # A session token isn't accepted in place of a stream token.
    assert client.get(f"/video_feed?stream_token={token}").status_code == 401


def test_video_feed_with_stream_token_streams(client, token):
    """A valid stream token opens the MJPEG stream."""
    st = get_stream_token(client, token)
    resp = client.get(f"/video_feed?stream_token={st}", buffered=False)
    assert resp.status_code == 200
    assert b"--frame" in next(resp.response)
    resp.close()


def test_stream_token_survives_duplicate_request_then_expires(client, token, clock):
    """A stream token works twice within 60 seconds (Safari needs this), then expires."""
    # Browsers may request the same <img> URL twice in a row (Safari does);
    # both must work or the Live Feed reconnect-loops.
    st = get_stream_token(client, token)
    client.get(f"/video_feed?stream_token={st}", buffered=False).close()
    second = client.get(f"/video_feed?stream_token={st}", buffered=False)
    assert second.status_code == 200
    second.close()

    st = get_stream_token(client, token)
    clock.advance(61)
    assert client.get(f"/video_feed?stream_token={st}").status_code == 401


def test_open_stream_ends_after_logout(client, token, monkeypatch):
    """An open video stream stops once its session is logged out."""
    import app as app_module
    monkeypatch.setattr(app_module, "STREAM_SESSION_CHECK_SECONDS", 0)
    st = get_stream_token(client, token)
    resp = client.get(f"/video_feed?stream_token={st}", buffered=False)
    chunks = iter(resp.response)
    next(chunks)
    client.post("/logout", headers=bearer(token))
    assert list(chunks) == []
