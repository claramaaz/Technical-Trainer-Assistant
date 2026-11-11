"""Create a user account, or reset its password (P7-35; FR-004, UC-05).

Usage (from the repository root, database running and migrated):
    python ingestion/create_user.py mia@example.com learner
    python ingestion/create_user.py admin@example.com admin
    python ingestion/create_user.py mia@example.com learner --reset-password

The password is typed at a prompt (twice), never on the command line, so it does not end up
in the shell history. Only its bcrypt hash is stored (backend/auth.py). There is no sign-up
page on purpose: accounts are created by whoever runs the system.
"""
import argparse
import getpass
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.auth import ROLES, hash_password  # noqa: E402
from migrate import connection_string  # noqa: E402


def save_user(conn, email, role, password_hash, reset=False):
    """Insert the user; with reset=True, update the password and role of an existing one.
    Returns "created", "updated", or "exists" (nothing changed)."""
    email = email.strip().lower()
    with conn.cursor() as cur:
        if reset:
            cur.execute("UPDATE users SET password_hash = %s, role = %s WHERE email = %s",
                        (password_hash, role, email))
            if cur.rowcount:
                conn.commit()
                return "updated"
        cur.execute("INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) "
                    "ON CONFLICT (email) DO NOTHING", (email, password_hash, role))
        conn.commit()
        return "created" if cur.rowcount else "exists"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("role", choices=ROLES)
    parser.add_argument("--reset-password", action="store_true",
                        help="change the password (and role) of an existing account")
    args = parser.parse_args(argv)

    password = getpass.getpass("Password (8 characters or more): ")
    if password != getpass.getpass("Same password again: "):
        sys.exit("The two passwords are different; nothing was saved.")
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        sys.exit(str(exc))

    with psycopg.connect(connection_string()) as conn:
        result = save_user(conn, args.email, args.role, password_hash, args.reset_password)
    if result == "exists":
        sys.exit(f"{args.email} already exists; use --reset-password to change it.")
    print(f"{result}: {args.email.strip().lower()} ({args.role})")


if __name__ == "__main__":
    main()
