"""Apply the numbered SQL files in db/migrations/ to the database, in order.

Usage (from the repository root, Docker database running):
    python ingestion/migrate.py

Connection: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT (and
optionally POSTGRES_HOST, default 127.0.0.1: "localhost" tries IPv6 first and
stalls for ~10 s because the container listens on IPv4 only), taken from the environment or, if not
set there, from the .env file (the same one docker-compose.yml uses).

Each file is applied once, in one transaction, and recorded in schema_migrations
with its checksum. Running it again applies only new files. If a file that was
already applied has changed, it stops with an error instead of ignoring the change.
"""
import hashlib
import os
import sys
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "db" / "migrations"
LOCK_ID = 7150001  # advisory lock: two migrate.py runs cannot interleave


def read_env_file(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def connection_string(environ=None, env_file=None):
    environ = os.environ if environ is None else environ
    file_values = read_env_file(ROOT / ".env" if env_file is None else env_file)

    def get(name, default=None):
        value = environ.get(name) or file_values.get(name) or default
        if value is None:
            sys.exit(f"{name} is not set (environment or .env); see .env.example")
        return value

    return make_conninfo(
        host=get("POSTGRES_HOST", "127.0.0.1"), port=get("POSTGRES_PORT", "5433"),
        user=get("POSTGRES_USER"), password=get("POSTGRES_PASSWORD"),
        dbname=get("POSTGRES_DB"), connect_timeout=10)


def checksum(path):
    # Line endings do not count, so CRLF/LF checkouts give the same checksum.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def migration_files(folder=MIGRATIONS):
    return sorted(folder.glob("[0-9][0-9][0-9]_*.sql"))


def migrate(conn, folder=MIGRATIONS):
    """Apply every new file in order; return the names applied this time."""
    applied_now = []
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            cur.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                               filename   text PRIMARY KEY,
                               checksum   text NOT NULL,
                               applied_at timestamptz NOT NULL DEFAULT now())""")
            conn.commit()
            cur.execute("SELECT filename, checksum FROM schema_migrations")
            done = dict(cur.fetchall())
            conn.commit()
            for path in migration_files(folder):
                digest = checksum(path)
                if path.name in done:
                    if done[path.name] != digest:
                        sys.exit(f"{path.name} was already applied but has changed; "
                                 "do not edit applied migrations, add a new file.")
                    continue
                with conn.transaction():
                    cur.execute(path.read_text(encoding="utf-8"))
                    cur.execute("INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                                (path.name, digest))
                applied_now.append(path.name)
        finally:
            conn.rollback()
            cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
            conn.commit()
    return applied_now


def main():
    with psycopg.connect(connection_string()) as conn:
        applied = migrate(conn)
    if applied:
        for name in applied:
            print(f"applied {name}")
    else:
        print("nothing to apply: database is up to date")


if __name__ == "__main__":
    main()
