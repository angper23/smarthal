"""Reset a SmartHal user's password from the terminal.

For when someone is locked out (forgot their password). Logged-in users
should use the Change Password screen in the app instead, which also
checks their current password.

    python reset_password.py

Prompts for the username and the new password (typed hidden, twice).
"""
import getpass
import sys

from auth import MAX_PASSWORD_BYTES, hash_password
from db import db_path, get_connection, init_db

MIN_PASSWORD_LENGTH = 8


def main():
    """Ask for a username and new password, then replace that user's bcrypt hash."""
    init_db()
    conn = get_connection()
    try:
        username = input("Username: ").strip()
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            names = [r["username"] for r in conn.execute("SELECT username FROM users ORDER BY username")]
            sys.exit(f"No user named {username!r}. Existing users: {', '.join(names) or '(none)'}")

        password = getpass.getpass("New password: ")
        if getpass.getpass("Confirm new password: ") != password:
            sys.exit("Passwords don't match.")
        if len(password) < MIN_PASSWORD_LENGTH:
            sys.exit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            sys.exit(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")

        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), row["id"]))
        conn.commit()
    finally:
        conn.close()

    print(f"Password reset for {username!r} in {db_path()}")
    # Sessions live in the running server's memory, which this script can't reach.
    print("Anyone already logged in as this user stays logged in until they log out, "
          "idle out, or the backend restarts.")


if __name__ == "__main__":
    main()
