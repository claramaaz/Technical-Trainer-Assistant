"""ingestion/create_user.py against a temporary database (skipped if PostgreSQL is not running)."""
import psycopg
import pytest

import create_user
import migrate
from backend.auth import check_password, hash_password


@pytest.fixture
def users_db(pg_test_dsn):
    with psycopg.connect(pg_test_dsn) as conn:
        migrate.migrate(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users")
        conn.commit()
        yield conn


def stored(conn, email):
    with conn.cursor() as cur:
        cur.execute("SELECT password_hash, role FROM users WHERE email = %s", (email,))
        return cur.fetchone()


def test_email_is_lower_cased_and_a_second_create_changes_nothing(users_db):
    assert create_user.save_user(users_db, " Mia@Test.com", "learner", hash_password("first-pass")) == "created"
    assert create_user.save_user(users_db, "mia@test.com", "admin", hash_password("other-pass")) == "exists"
    password_hash, role = stored(users_db, "mia@test.com")
    assert role == "learner" and check_password("first-pass", password_hash)


def test_reset_password_changes_password_and_role(users_db):
    create_user.save_user(users_db, "mia@test.com", "learner", hash_password("first-pass"))
    assert create_user.save_user(users_db, "mia@test.com", "admin", hash_password("new-pass-1"), reset=True) == "updated"
    password_hash, role = stored(users_db, "mia@test.com")
    assert role == "admin" and check_password("new-pass-1", password_hash)


def test_database_refuses_an_unknown_role(users_db):
    with pytest.raises(psycopg.errors.CheckViolation):
        create_user.save_user(users_db, "x@test.com", "superuser", hash_password("whatever-1"))
    users_db.rollback()
