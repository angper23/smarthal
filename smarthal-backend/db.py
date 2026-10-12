"""SQLite database access. The database is one file, data/dev.db by default (set DB_PATH to change it)."""

import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BACKEND_DIR, "schema.sql")


def db_path():
    """Return the database file path from DB_PATH. Relative paths resolve from this folder."""
    # Read at call time (not import time) so tests can point DB_PATH at a
    # temporary file. Relative paths resolve against this folder, so the DB
    # lands in the same place regardless of where python was started from.
    path = os.environ.get("DB_PATH", "data/dev.db")
    if not os.path.isabs(path):
        path = os.path.join(BACKEND_DIR, path)
    return path


def get_connection():
    """Open a database connection with foreign keys on. Rows can be read like dicts: row['username']."""
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # SQLite ships with foreign keys off, and the setting is per connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create any missing tables from schema.sql. Safe to run on every startup."""
    # utf-8 explicitly: Windows otherwise reads files with its own legacy encoding
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = f.read()
    conn = get_connection()
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized database at {db_path()}")
