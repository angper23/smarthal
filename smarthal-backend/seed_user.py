"""Create one SmartHal user account.

Accounts come from this script for now (there's no sign-up screen yet).
Prompts for anything not set in the environment:

    python seed_user.py
    SEED_USERNAME=alex SEED_ROLE=admin python seed_user.py   # still prompts for the password

SEED_PASSWORD is also read if set (handy for scripts), but prefer the prompt
so the password doesn't end up in your shell history.
"""
import getpass
import os
import sqlite3
import sys

from auth import MAX_PASSWORD_BYTES, hash_password
from db import db_path, get_connection, init_db

ROLES = ("home_user", "admin")
MIN_PASSWORD_LENGTH = 8


def prompt_password():
    """Return SEED_PASSWORD if set; otherwise ask twice (hidden) and make sure they match."""
    password = os.environ.get("SEED_PASSWORD")
    if password:
        return password
    password = getpass.getpass("Password: ")
    if getpass.getpass("Confirm password: ") != password:
        sys.exit("Passwords don't match.")
    return password


def main():
    """Ask for username, password and role, then save the new user with a bcrypt-hashed password."""
    username = (os.environ.get("SEED_USERNAME") or input("Username: ")).strip()
    if not username:
        sys.exit("Username is required.")

    password = prompt_password()
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        sys.exit(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")

    role = (os.environ.get("SEED_ROLE") or input("Role [home_user/admin] (home_user): ")).strip()
    role = role or "home_user"
    if role not in ROLES:
        sys.exit(f"Role must be one of: {', '.join(ROLES)}")

    email = (os.environ.get("SEED_EMAIL") or "").strip() or None

    init_db()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, email, role) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), email, role),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        sys.exit(f"A user named {username!r} already exists.")
    finally:
        conn.close()

    print(f"Created {role} {username!r} in {db_path()}")


if __name__ == "__main__":
    main()
