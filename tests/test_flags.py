"""Tests for the "Wrong figure" reports (P7-38), written from UC-03 and FR-003:
"System stores the flag with the figure, the query, the user and the time", "adds the figure to
the admin QA queue", and A1 "no duplicate entry is created".

The API tests replace backend/flags.py by fakes (no database). The database tests use a made-up
handbook in the temporary database (tests/test_load_db.py); they are skipped if PostgreSQL is
not running.   Run:   python -m pytest -q tests/test_flags.py
"""
import time

import psycopg
import pytest
from fastapi.testclient import TestClient

import load_db
from backend import auth, flags
from backend.app import app
from test_load_db import HID, MODEL, make_handbook

client = TestClient(app)


# --- API, with backend/flags.py replaced by fakes --------------------------------------------

@pytest.fixture
def saved(monkeypatch):
    """Record what the endpoint asks to save; answer with `saved.result` (CREATED by default)."""
    calls = []

    def fake_save(figure_id, user_id, query, reason=None):
        calls.append((figure_id, user_id, query, reason))
        return fake_save.result

    fake_save.result = flags.CREATED
    fake_save.calls = calls
    monkeypatch.setattr(flags, "save_flag", fake_save)
    return fake_save


def test_report_stores_figure_question_user_and_reason(saved):
    r = client.post("/flags", json={"figure_id": 55, "query": "  four forces  ", "reason": "  wrong diagram "})
    assert r.status_code == 201 and r.json() == {"status": "reported"}
    # user 0 is the logged-in Learner of conftest.py; question and reason are trimmed
    assert saved.calls == [(55, 0, "four forces", "wrong diagram")]


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reason_is_optional(saved, reason):
    body = {"figure_id": 55, "query": "four forces"}
    if reason is not None:
        body["reason"] = reason
    assert client.post("/flags", json=body).status_code == 201
    assert saved.calls[0][3] is None


def test_second_report_says_already_reported(saved):
    saved.result = flags.DUPLICATE
    r = client.post("/flags", json={"figure_id": 55, "query": "four forces"})
    assert r.status_code == 200 and r.json() == {"status": "already_reported"}


def test_unknown_figure_is_404(saved):
    saved.result = flags.UNKNOWN_FIGURE
    assert client.post("/flags", json={"figure_id": 999999, "query": "four forces"}).status_code == 404


def test_deleted_account_is_401(saved):
    saved.result = flags.UNKNOWN_USER
    assert client.post("/flags", json={"figure_id": 55, "query": "four forces"}).status_code == 401


@pytest.mark.parametrize("body", [
    {"query": "four forces"},                                   # no figure
    {"figure_id": 0, "query": "four forces"},                   # not a database id
    {"figure_id": 55},                                          # no question
    {"figure_id": 55, "query": ""},
    {"figure_id": 55, "query": "   "},
    {"figure_id": 55, "query": "q" * 501},
    {"figure_id": 55, "query": "four forces", "reason": "r" * 501},
])
def test_bad_report_is_422_and_nothing_is_saved(saved, body):
    assert client.post("/flags", json=body).status_code == 422
    assert saved.calls == []


@pytest.mark.real_auth
def test_report_without_login_is_401(saved):
    assert client.post("/flags", json={"figure_id": 55, "query": "four forces"}).status_code == 401
    assert saved.calls == []


@pytest.mark.real_auth
def test_learner_cannot_read_the_qa_queue(monkeypatch):
    monkeypatch.setattr(flags, "open_flags", lambda: pytest.fail("must not be read"))
    token = auth.make_token({"id": 1, "email": "learner@test.com", "role": "learner"})
    r = client.get("/admin/flags", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.real_auth
def test_admin_reads_the_qa_queue(monkeypatch):
    monkeypatch.setattr(flags, "open_flags", lambda: [{"id": 1, "figure_number": "4-3"}])
    token = auth.make_token({"id": 2, "email": "admin@test.com", "role": "admin"})
    r = client.get("/admin/flags", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json() == {"flags": [{"id": 1, "figure_number": "4-3"}]}


# --- database --------------------------------------------------------------------------------

@pytest.fixture
def flag_db(db, pg_test_dsn, tmp_path, monkeypatch):
    """A loaded made-up handbook, two users and no reports, in the temporary database."""
    make_handbook(tmp_path)
    load_db.load(db, load_db.read_sources(HID, MODEL, tmp_path))
    users = {}
    for email in ("learner-a@test.com", "learner-b@test.com"):
        users[email] = db.execute(
            "INSERT INTO users (email, password_hash, role) VALUES (%s, 'x', 'learner') "
            "ON CONFLICT (email) DO UPDATE SET role = 'learner' RETURNING id", (email,)).fetchone()[0]
    db.execute("DELETE FROM figure_flags")
    db.commit()
    monkeypatch.setattr(flags, "DSN", pg_test_dsn)
    figures = dict(db.execute("SELECT figure_number, id FROM figures").fetchall())
    return db, figures, users["learner-a@test.com"], users["learner-b@test.com"]


def stored(db):
    db.commit()   # new snapshot: see the rows written by flags.py's own connection
    return db.execute("SELECT figure_id, user_id, query, reason, status, flagged_at "
                      "FROM figure_flags ORDER BY id").fetchall()


def test_report_is_stored_open_with_question_user_and_time(flag_db):
    db, figures, a, _ = flag_db
    before = time.time()
    assert flags.save_flag(figures["1-1"], a, "Four forces", "shows the wrong aircraft") == flags.CREATED
    [(figure_id, user_id, query, reason, status, flagged_at)] = stored(db)
    assert (figure_id, user_id, query, reason, status) == (figures["1-1"], a, "Four forces",
                                                         "shows the wrong aircraft", "open")
    assert before - 5 <= flagged_at.timestamp() <= time.time() + 5


def test_same_learner_same_figure_same_question_is_one_report(flag_db):
    db, figures, a, b = flag_db
    assert flags.save_flag(figures["1-1"], a, "four forces") == flags.CREATED
    assert flags.save_flag(figures["1-1"], a, "FOUR forces") == flags.DUPLICATE      # UC-03 A1
    assert flags.save_flag(figures["1-1"], b, "four forces") == flags.CREATED        # another learner
    assert flags.save_flag(figures["1-1"], a, "lift and drag") == flags.CREATED      # another question
    assert flags.save_flag(figures["1-2"], a, "four forces") == flags.CREATED        # another figure
    assert len(stored(db)) == 4


def test_unknown_figure_is_not_stored(flag_db):
    db, _, a, _ = flag_db
    assert flags.save_flag(987654, a, "four forces") == flags.UNKNOWN_FIGURE
    assert stored(db) == []


def test_unknown_user_is_not_stored(flag_db):
    db, figures, _, _ = flag_db
    assert flags.save_flag(figures["1-1"], 987654, "four forces") == flags.UNKNOWN_USER
    assert stored(db) == []


def test_qa_queue_lists_open_reports_newest_first_with_what_the_admin_needs(flag_db):
    db, figures, a, b = flag_db
    flags.save_flag(figures["1-1"], a, "four forces", "wrong diagram")
    flags.save_flag(figures["1-1"], b, "lift")
    flags.save_flag(figures["1-2"], a, "drag")
    queue = flags.open_flags()
    assert [q["query"] for q in queue] == ["drag", "lift", "four forces"]
    first = queue[-1]
    assert first["figure_number"] == "1-1" and first["reported_by"] == "learner-a@test.com"
    assert first["reason"] == "wrong diagram" and first["reports_for_figure"] == 2
    assert first["caption"] and first["handbook"] and first["printed_page"]
    assert first["image_url"] == f"/figures/{figures['1-1']}/image"


def test_resolved_reports_leave_the_queue(flag_db):
    db, figures, a, _ = flag_db
    flags.save_flag(figures["1-1"], a, "four forces")
    db.execute("UPDATE figure_flags SET status = 'resolved'")
    db.commit()
    assert flags.open_flags() == []


def test_database_refuses_an_unknown_status(flag_db):
    db, figures, a, _ = flag_db
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("INSERT INTO figure_flags (figure_id, user_id, query, status) VALUES (%s, %s, 'q', 'deleted')",
                   (figures["1-1"], a))
    db.rollback()
