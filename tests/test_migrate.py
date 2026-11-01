"""Tests for ingestion/migrate.py on a temporary database (skipped if PostgreSQL is not running).

Run from the repository root:   python -m pytest -q tests/test_migrate.py

The migration files used here are small temporary ones written by the test, not the
real db/migrations/001_init.sql.
"""
import psycopg
import pytest

import migrate


def table_exists(conn, name):
    row = conn.execute("SELECT to_regclass(%s)", (name,)).fetchone()
    conn.commit()
    return row[0] is not None


@pytest.fixture
def clean(empty_database_dsn):
    """A connection to a new empty database (its own, so the shared test database is untouched)."""
    with psycopg.connect(empty_database_dsn) as conn:
        yield conn
        conn.rollback()


def test_a_migration_failing_halfway_rolls_back_only_that_file(clean, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE demo_a (id int);", encoding="utf-8")
    # The first statement works, the second fails: demo_b must not survive.
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE demo_b (id int);\nSELECT 1/0;", encoding="utf-8")
    (tmp_path / "003_never.sql").write_text("CREATE TABLE demo_never (id int);", encoding="utf-8")

    with pytest.raises(psycopg.errors.DivisionByZero):
        migrate.migrate(clean, tmp_path)

    clean.rollback()
    assert table_exists(clean, "demo_a")            # the earlier file stays applied
    assert not table_exists(clean, "demo_b")        # the failing file left nothing behind
    assert not table_exists(clean, "demo_never")    # and the later file was not tried
    applied = [r[0] for r in clean.execute("SELECT filename FROM schema_migrations ORDER BY filename")]
    assert applied == ["001_ok.sql"]                # the failed file is not recorded


def test_after_fixing_the_failed_file_the_next_run_applies_it(clean, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE demo_a (id int);", encoding="utf-8")
    bad = tmp_path / "002_bad.sql"
    bad.write_text("CREATE TABLE demo_b (id int);\nSELECT 1/0;", encoding="utf-8")
    with pytest.raises(psycopg.errors.DivisionByZero):
        migrate.migrate(clean, tmp_path)
    clean.rollback()

    bad.write_text("CREATE TABLE demo_b (id int);", encoding="utf-8")  # never applied, so editing it is allowed
    assert migrate.migrate(clean, tmp_path) == ["002_bad.sql"]
    assert table_exists(clean, "demo_b")


def test_second_run_applies_nothing_and_an_edited_applied_file_is_refused(clean, tmp_path):
    first = tmp_path / "001_ok.sql"
    first.write_text("CREATE TABLE demo_a (id int);", encoding="utf-8")
    assert migrate.migrate(clean, tmp_path) == ["001_ok.sql"]
    assert migrate.migrate(clean, tmp_path) == []

    first.write_text("CREATE TABLE demo_a (id int, extra int);", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        migrate.migrate(clean, tmp_path)
    assert "already applied but has changed" in str(exc.value)


def test_line_endings_do_not_change_the_checksum(tmp_path):
    lf = tmp_path / "a.sql"
    crlf = tmp_path / "b.sql"
    lf.write_bytes(b"SELECT 1;\nSELECT 2;\n")
    crlf.write_bytes(b"SELECT 1;\r\nSELECT 2;\r\n")
    assert migrate.checksum(lf) == migrate.checksum(crlf)
