"""Tests for the good / bad rating of a chat answer (P7-53), written from FR-010: "store the rating with
the question it answers (query log id), the user and the time, one rating per user and answer (it can
be changed)" and "a learner cannot read the admin list (403)".

The API tests replace backend/ratings.py by a fake (no database). The database tests use the
temporary database; they are skipped if PostgreSQL is not running.
Run:   python -m pytest -q tests/test_ratings.py
"""
import time

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend import analytics, auth, ratings
from backend.app import app

client = TestClient(app)


# --- API, with backend/ratings.py replaced by a fake ------------------------------------------

@pytest.fixture
def saved(monkeypatch):
    calls = []

    def fake_save(query_id, user_id, rating):
        calls.append((query_id, user_id, rating))
        return fake_save.result

    fake_save.result = ratings.SAVED
    fake_save.calls = calls
    monkeypatch.setattr(ratings, "save_rating", fake_save)
    return fake_save


@pytest.mark.parametrize("rating", ["good", "bad"])
def test_rating_is_stored_with_the_answer_and_the_user(saved, rating):
    r = client.post("/ratings", json={"query_id": 12, "rating": rating})
    assert r.status_code == 200 and r.json() == {"status": "saved", "rating": rating}
    assert saved.calls == [(12, 0, rating)]          # user 0 = the logged-in Learner of conftest.py


def test_unknown_answer_is_404(saved):
    saved.result = ratings.UNKNOWN_ANSWER
    assert client.post("/ratings", json={"query_id": 999, "rating": "good"}).status_code == 404


def test_deleted_account_is_401(saved):
    saved.result = ratings.UNKNOWN_USER
    assert client.post("/ratings", json={"query_id": 12, "rating": "good"}).status_code == 401


@pytest.mark.parametrize("body", [
    {"rating": "good"},                       # no answer
    {"query_id": 0, "rating": "good"},        # not a log id
    {"query_id": 12},                         # no rating
    {"query_id": 12, "rating": "ok"},         # only good or bad
    {"query_id": 12, "rating": ""},
])
def test_bad_rating_is_422_and_nothing_is_saved(saved, body):
    assert client.post("/ratings", json=body).status_code == 422
    assert saved.calls == []


@pytest.mark.real_auth
def test_rating_without_login_is_401(saved):
    assert client.post("/ratings", json={"query_id": 12, "rating": "good"}).status_code == 401
    assert saved.calls == []


@pytest.mark.real_auth
def test_learner_cannot_read_the_admin_analytics(monkeypatch):
    monkeypatch.setattr(analytics, "summary", lambda *a, **k: pytest.fail("must not be read"))
    token = auth.make_token({"id": 1, "email": "learner@test.com", "role": "learner"})
    r = client.get("/admin/analytics?from=2026-11-01&to=2026-11-18", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


# --- database --------------------------------------------------------------------------------

@pytest.fixture
def rating_db(db, pg_test_dsn, monkeypatch):
    """Two learners and three logged questions (two chat answers, one /search), no ratings."""
    db.execute("DELETE FROM answer_ratings")
    db.execute("DELETE FROM query_log")
    users = [db.execute("INSERT INTO users (email, password_hash, role) VALUES (%s, 'x', 'learner') "
                        "ON CONFLICT (email) DO UPDATE SET role = 'learner' RETURNING id", (e,)).fetchone()[0]
             for e in ("rate-a@test.com", "rate-b@test.com")]
    ids = [db.execute("INSERT INTO query_log (endpoint, query, outcome, latency_ms) VALUES (%s, %s, 'answered', 100) "
                      "RETURNING id", (endpoint, q)).fetchone()[0]
           for endpoint, q in (("chat", "four forces"), ("chat", "and lift?"), ("search", "drag"))]
    db.commit()
    monkeypatch.setattr(ratings, "DSN", pg_test_dsn)
    return db, users, ids


def stored(db):
    db.commit()   # new snapshot: see the rows written by ratings.py's own connection
    return db.execute("SELECT query_id, user_id, rating, rated_at FROM answer_ratings ORDER BY query_id, user_id").fetchall()


def test_rating_is_stored_with_answer_user_and_time(rating_db):
    db, (a, _), (chat1, _, _) = rating_db
    before = time.time()
    assert ratings.save_rating(chat1, a, "bad") == ratings.SAVED
    [(query_id, user_id, rating, rated_at)] = stored(db)
    assert (query_id, user_id, rating) == (chat1, a, "bad")
    assert before - 5 <= rated_at.timestamp() <= time.time() + 5


def test_rating_again_changes_it_and_never_makes_two_rows(rating_db):
    db, (a, b), (chat1, chat2, _) = rating_db
    ratings.save_rating(chat1, a, "good")
    ratings.save_rating(chat1, a, "bad")                    # FR-010: it can be changed
    ratings.save_rating(chat1, b, "good")                   # another learner
    ratings.save_rating(chat2, a, "good")                   # another answer
    assert [(q, u, r) for q, u, r, _ in stored(db)] == [(chat1, a, "bad"), (chat1, b, "good"), (chat2, a, "good")]


def test_unknown_or_non_chat_answer_is_not_stored(rating_db):
    db, (a, _), (_, _, search_row) = rating_db
    assert ratings.save_rating(987654, a, "good") == ratings.UNKNOWN_ANSWER
    assert ratings.save_rating(search_row, a, "good") == ratings.UNKNOWN_ANSWER   # no buttons on /search
    assert stored(db) == []


def test_unknown_user_is_not_stored(rating_db):
    db, _, (chat1, _, _) = rating_db
    assert ratings.save_rating(chat1, 987654, "good") == ratings.UNKNOWN_USER
    assert stored(db) == []


def test_database_refuses_another_rating(rating_db):
    db, (a, _), (chat1, _, _) = rating_db
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute("INSERT INTO answer_ratings (query_id, user_id, rating) VALUES (%s, %s, 'meh')", (chat1, a))
    db.rollback()
