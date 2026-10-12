-- SmartHal database schema (SQLite). Safe to run repeatedly.
-- Sessions are intentionally not stored here: they live in memory (auth.py).

-- Login accounts. password_hash is bcrypt; the real password is never stored.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    email         TEXT,
    role          TEXT    NOT NULL DEFAULT 'home_user'
                          CHECK (role IN ('home_user', 'admin'))
);

-- rtsp_url stays NULL: the real URL (with the camera password) lives in .env.
CREATE TABLE IF NOT EXISTS cameras (
    id                    INTEGER PRIMARY KEY,
    ip_address            TEXT,
    rtsp_url              TEXT,
    status                TEXT DEFAULT 'offline',
    sensitivity_threshold REAL
);

-- People registered as residents (Register Resident, a later sprint).
CREATE TABLE IF NOT EXISTS residents (
    id               INTEGER PRIMARY KEY,
    registered_by    INTEGER NOT NULL REFERENCES users(id),
    name             TEXT    NOT NULL,
    facial_embedding BLOB,
    photo_path       TEXT
);

-- Each time the camera sees a face (Event History, a later sprint).
CREATE TABLE IF NOT EXISTS detection_events (
    id                INTEGER PRIMARY KEY,
    camera_id         INTEGER NOT NULL REFERENCES cameras(id),
    resident_id       INTEGER REFERENCES residents(id), -- NULL = Unknown
    timestamp         TEXT    NOT NULL,
    classification    TEXT    NOT NULL CHECK (classification IN ('Resident', 'Unknown')),
    snapshot_path     TEXT,
    clip_path         TEXT,
    clip_duration_sec INTEGER DEFAULT 10
);

-- Notifications sent about a detection event (a later sprint).
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY,
    event_id        INTEGER NOT NULL REFERENCES detection_events(id),
    sent_at         TEXT,
    delivery_method TEXT,
    status          TEXT
);

-- Each user's alert preferences, one row per user (Alert Settings, a later sprint).
CREATE TABLE IF NOT EXISTS alert_settings (
    id              INTEGER PRIMARY KEY,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id),
    alert_type      TEXT    DEFAULT 'email',
    conditions      TEXT    DEFAULT 'unknown_only',
    cooldown_period INTEGER DEFAULT 60
);
