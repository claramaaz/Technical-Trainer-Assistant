"""Shared fixtures for the search-slice tests (real data and real model; skipped if the data is absent)."""
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EMB = ROOT / "data" / "extracted" / "FAA-H-8083-15B" / "figure_embeddings_full_BAAI_bge-small-en-v1.5.npy"


@pytest.fixture(scope="session")
def questions():
    with open(ROOT / "evaluation" / "questions.csv", encoding="utf-8-sig", newline="") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


@pytest.fixture(scope="session")
def real_index():
    if not EMB.exists():
        pytest.skip("data/extracted/... figure embeddings missing: run evaluation/figure_retrieval.py embed")
    from backend.retrieval import load_index
    return load_index()


# ---------------------------------------------------------------------------
# PostgreSQL fixtures (migration and loader tests). They use a separate, temporary
# database, never the real one, and skip with a message if Postgres is not running.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "ingestion"))


@pytest.fixture(scope="session")
def pg_test_dsn():
    import uuid

    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    import migrate

    base = migrate.connection_string()
    try:
        admin = psycopg.connect(make_conninfo(base, connect_timeout=3), autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not running ({str(exc).strip()[:80]}); start it with: docker compose up -d")
    name = "p7_test_" + uuid.uuid4().hex[:8]
    admin.execute(f'CREATE DATABASE "{name}"')
    dsn = make_conninfo(base, dbname=name)
    yield dsn
    admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    admin.close()
    assert conninfo_to_dict(dsn)["dbname"] == name


@pytest.fixture
def db(pg_test_dsn):
    """A connection to the temporary database with the real migrations applied and every table empty."""
    import psycopg

    import migrate

    with psycopg.connect(pg_test_dsn) as conn:
        migrate.migrate(conn)
        conn.execute("TRUNCATE documents CASCADE")
        conn.commit()
        yield conn
        conn.rollback()


@pytest.fixture
def empty_database_dsn(pg_test_dsn):
    """A brand-new empty temporary database (for tests that must not touch the shared one)."""
    import uuid

    import psycopg
    from psycopg.conninfo import make_conninfo

    name = "p7_test_" + uuid.uuid4().hex[:8]
    with psycopg.connect(make_conninfo(pg_test_dsn, dbname="postgres"), autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}"')
        yield make_conninfo(pg_test_dsn, dbname=name)
        admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
