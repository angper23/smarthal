"""Login security helpers: password hashing, sessions, stream tokens and rate limiting.

Sessions and stream tokens live in memory (a restart logs everyone out). Only password
hashes are stored in the database.
"""

import secrets
import threading
import time
from collections import defaultdict, deque
from functools import wraps

import bcrypt
from flask import current_app, g, jsonify, request

# SRS §5.2: sessions expire after 30 minutes without activity.
SESSION_IDLE_SECONDS = 30 * 60

# The <img> tag can't send an Authorization header, so /video_feed takes a
# separate token in its query string instead. Query strings end up in
# browser history and proxy logs, so this token only lives long enough to
# open a stream, and can't be used for anything else.
STREAM_TOKEN_SECONDS = 60

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 15 * 60

# bcrypt only looks at the first 72 bytes of a password (and bcrypt>=5
# raises instead of silently truncating), so longer ones are rejected.
MAX_PASSWORD_BYTES = 72


def hash_password(password):
    """Return a bcrypt hash of the password. Salted and one-way, so it's safe to store."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


# Checked against when the username doesn't exist, so a login attempt for an
# unknown user takes about as long as one for a real user with a wrong
# password, and response timing doesn't reveal which usernames are valid.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_password(password, password_hash):
    """Constant-work password check. password_hash=None means "no such
    user": the comparison still runs, against a dummy hash, and fails."""
    pw = password.encode("utf-8")
    if len(pw) > MAX_PASSWORD_BYTES:
        pw = pw[:MAX_PASSWORD_BYTES]
        password_hash = None  # no stored password can be this long
    target = (password_hash or _DUMMY_HASH).encode("ascii")
    matched = bcrypt.checkpw(pw, target)
    return matched and password_hash is not None


class SessionStore:
    """In-memory sessions and stream tokens. Lost on restart, which is
    acceptable for the prototype (everyone just logs in again)."""

    def __init__(self, clock=time.monotonic):
        """clock: where the current time comes from (tests pass a fake clock)."""
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions = {}       # token -> {"user": {...}, "last_seen": t}
        self._stream_tokens = {}  # stream_token -> {"session": token, "expires_at": t}

    def create(self, user):
        """Start a session for this user and return its new random token."""
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._prune()
            self._sessions[token] = {"user": dict(user), "last_seen": self._clock()}
        return token

    def touch(self, token):
        """Return the session's user and mark it active, or None if the
        token is unknown or has been idle too long."""
        with self._lock:
            session = self._live_session(token)
            if session is None:
                return None
            session["last_seen"] = self._clock()
            return dict(session["user"])

    def is_active(self, token):
        """Like touch(), but doesn't count as activity. Used by the video
        stream's periodic re-check, so an open stream alone can't keep a
        session alive forever."""
        with self._lock:
            return self._live_session(token) is not None

    def revoke(self, token):
        """End one session (used by logout)."""
        with self._lock:
            self._revoke(token)

    def revoke_other_sessions(self, user_id, keep_token):
        """End every session for this user except keep_token. Used after a
        password change, so anyone still logged in with the old password
        (another device, or someone who'd taken over a session) is signed
        out — and their open video streams end at the next 5-second check."""
        with self._lock:
            for token in [t for t, s in self._sessions.items()
                          if s["user"]["id"] == user_id and t != keep_token]:
                self._revoke(token)

    # Callers must hold self._lock.
    def _revoke(self, token):
        """Remove a session and any stream tokens issued for it. Caller must hold the lock."""
        self._sessions.pop(token, None)
        for st in [k for k, v in self._stream_tokens.items() if v["session"] == token]:
            del self._stream_tokens[st]

    def create_stream_token(self, session_token):
        """Issue a 60-second stream token tied to this session."""
        stream_token = secrets.token_urlsafe(32)
        with self._lock:
            self._stream_tokens[stream_token] = {
                "session": session_token,
                "expires_at": self._clock() + STREAM_TOKEN_SECONDS,
            }
        return stream_token

    def redeem_stream_token(self, stream_token):
        """Returns the session token the stream token was issued for, or
        None if it's unknown, expired, or its session ended.

        Deliberately not single-use: some browsers (Safari) request an <img>
        URL twice in a row, and a single-use token made the second request
        fail, which the Live Feed treated as a dropped stream and reconnected
        forever. The token is still short-lived and bound to one session,
        and the session is re-checked every few seconds while streaming."""
        with self._lock:
            entry = self._stream_tokens.get(stream_token)
            if entry is None:
                return None
            if entry["expires_at"] <= self._clock():
                del self._stream_tokens[stream_token]
                return None
            if self._live_session(entry["session"]) is None:
                return None
            return entry["session"]

    # Callers must hold self._lock.
    def _live_session(self, token):
        """Return the session if it exists and hasn't been idle 30+ minutes.

        An idle-expired session is deleted. Caller must hold the lock.
        """
        if not token:
            return None
        session = self._sessions.get(token)
        if session is None:
            return None
        if self._clock() - session["last_seen"] > SESSION_IDLE_SECONDS:
            del self._sessions[token]
            return None
        return session

    def _prune(self):
        """Drop expired sessions and stream tokens so memory doesn't grow. Caller must hold the lock."""
        now = self._clock()
        for token in [t for t, s in self._sessions.items()
                      if now - s["last_seen"] > SESSION_IDLE_SECONDS]:
            del self._sessions[token]
        for st in [k for k, v in self._stream_tokens.items() if v["expires_at"] <= now]:
            del self._stream_tokens[st]


class LoginRateLimiter:
    """Counts failed logins per (username, client IP) in a sliding window."""

    def __init__(self, clock=time.monotonic):
        """clock: where the current time comes from (tests pass a fake clock)."""
        self._clock = clock
        self._lock = threading.Lock()
        self._failures = defaultdict(deque)

    def retry_after(self, key):
        """Seconds until another attempt is allowed, or 0 if allowed now."""
        with self._lock:
            failures = self._recent(key)
            if not failures:
                # Don't keep an empty entry around for every username tried
                del self._failures[key]
            if len(failures) < LOGIN_MAX_FAILURES:
                return 0
            return max(1, int(failures[0] + LOGIN_WINDOW_SECONDS - self._clock()) + 1)

    def record_failure(self, key):
        """Count one failed attempt for this key."""
        with self._lock:
            self._recent(key).append(self._clock())

    def reset(self, key):
        """Forget all failures for this key (called after a success)."""
        with self._lock:
            self._failures.pop(key, None)

    def _recent(self, key):
        """Return this key's failures inside the window, dropping older ones. Caller must hold the lock."""
        failures = self._failures[key]
        cutoff = self._clock() - LOGIN_WINDOW_SECONDS
        while failures and failures[0] <= cutoff:
            failures.popleft()
        return failures


def bearer_token():
    """Return the token from an 'Authorization: Bearer <token>' header, or None."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def require_auth(view):
    """Route decorator: answer 401 unless the request carries a valid session token.

    On success it sets g.user and g.session_token for the route to use.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        """Check the token, then run the wrapped route."""
        token = bearer_token()
        user = current_app.extensions["sessions"].touch(token)
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        g.session_token = token
        g.user = user
        return view(*args, **kwargs)

    return wrapper
