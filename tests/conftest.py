"""Shared fixtures for the search-slice tests (real data and real model; skipped if the data is absent)."""
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def rank_fake_indexes_with_numpy(monkeypatch):
    """A FakeIndex (tests/fake_index.py) is ranked with numpy; any other index goes to the real rank() (database)."""
    from backend import retrieval
    from fake_index import FakeIndex, numpy_rank
    real_rank = retrieval.rank
    monkeypatch.setattr(retrieval, "rank", lambda index, q, k, handbooks=None: (
        numpy_rank if isinstance(index, FakeIndex) else real_rank)(index, q, k, handbooks))


@pytest.fixture(autouse=True)
def text_mode_unless_a_test_chooses(monkeypatch):
    """Tests do not depend on RETRIEVAL_MODE in the developer's .env (P7-30): text mode by default."""
    monkeypatch.setenv("RETRIEVAL_MODE", "text")


def pytest_configure(config):
    config.addinivalue_line("markers", "real_auth: use the real login checks (tests/test_auth.py)")


@pytest.fixture(autouse=True)
def test_jwt_secret(monkeypatch):
    """Tokens in tests are signed with a fixed test key, never the developer's JWT_SECRET (P7-35)."""
    monkeypatch.setenv("JWT_SECRET", "test-secret-only-for-pytest-0123456789abcdef")


@pytest.fixture(autouse=True)
def logged_in_as_learner(request):
    """Since P7-35 every API route except /health needs a logged-in user. The API tests written
    before it test retrieval, not login, so they run as a logged-in Learner: FastAPI's
    dependency_overrides replaces the login check for the duration of the test.
    Tests marked real_auth (tests/test_auth.py) get the real check instead."""
    if request.node.get_closest_marker("real_auth"):
        yield
        return
    from backend import auth
    from backend.app import app
    app.dependency_overrides[auth.current_user] = lambda: {"id": 0, "email": "test@learner", "role": "learner"}
    yield
    app.dependency_overrides.pop(auth.current_user, None)


@pytest.fixture(autouse=True)
def no_query_log_in_real_database(monkeypatch):
    """Tests must not write test questions into the real query_log (P7-28). tests/test_query_log.py
    turns the log back on, pointed at the temporary database."""
    from backend import query_log
    monkeypatch.setattr(query_log, "ENABLED", False)


@pytest.fixture(scope="session")
def questions():
    with open(ROOT / "evaluation" / "questions.csv", encoding="utf-8-sig", newline="") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


@pytest.fixture(scope="session")
def real_index():
    """The search index of the real database (read only). Skipped if PostgreSQL or the data is missing."""
    import psycopg

    from backend.retrieval import load_index
    try:
        index = load_index()
    except psycopg.OperationalError as exc:
        pytest.skip(f"PostgreSQL is not running ({str(exc).strip()[:80]}); start it with: docker compose up -d")
    except psycopg.errors.UndefinedTable:
        pytest.skip("the database has no tables: run python ingestion/migrate.py")
    if not index.documents:
        pytest.skip("no searchable figures in the database: run python ingestion/load_db.py FAA-H-8083-15B")
    return index


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
