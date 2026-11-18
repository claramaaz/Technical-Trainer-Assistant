"""Tests for the admin analytics (P7-43), written from FR-007 ("for a period chosen by the admin: query
volume, latency, failure rate (questions ending in an error) and the list of questions for which no
answer was found"), UC-09 (A1: no queries in the period -> empty state) and FR-010 (rating counts and
the list of bad responses with their question).

The database tests write a made-up query log in the temporary database; they are skipped if
PostgreSQL is not running.   Run:   python -m pytest -q tests/test_analytics.py
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend import analytics, auth
from backend.app import app

client = TestClient(app)


def admin_headers():
    # made inside each test: the test JWT_SECRET is set by a fixture of conftest.py
    return {"Authorization": f"Bearer {auth.make_token({'id': 2, 'email': 'admin@test.com', 'role': 'admin'})}"}


# --- the period -----------------------------------------------------------------------------

def test_period_checks():
    today = date(2026, 11, 18)
    assert analytics.check_period(date(2026, 11, 1), date(2026, 11, 18), today) == (date(2026, 11, 1), date(2026, 11, 18))
    with pytest.raises(analytics.PeriodError):
        analytics.check_period(date(2026, 11, 18), date(2026, 11, 1), today)      # end before start
    with pytest.raises(analytics.PeriodError):
        analytics.check_period(date(2026, 11, 19), date(2026, 11, 20), today)     # in the future
    with pytest.raises(analytics.PeriodError):
        analytics.check_period(date(2024, 1, 1), date(2026, 11, 18), today)       # too long


@pytest.mark.real_auth
@pytest.mark.parametrize("query", ["from=2026-11-18&to=2026-11-01", "from=yesterday&to=2026-11-18", "to=2026-11-18"])
def test_bad_period_is_422(monkeypatch, query):
    monkeypatch.setattr(analytics, "summary", lambda *a, **k: pytest.fail("must not be read"))
    assert client.get(f"/admin/analytics?{query}", headers=admin_headers()).status_code == 422


@pytest.mark.real_auth
def test_admin_gets_the_summary_of_the_period(monkeypatch):
    asked = []
    monkeypatch.setattr(analytics, "summary", lambda start, end: asked.append((start, end)) or {"ok": True})
    r = client.get("/admin/analytics?from=2026-11-01&to=2026-11-07", headers=admin_headers())
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert asked == [(date(2026, 11, 1), date(2026, 11, 7))]


# --- database --------------------------------------------------------------------------------

DAY = date(2026, 11, 10)


def at(day_offset, hour=12):
    return datetime(DAY.year, DAY.month, DAY.day, hour, tzinfo=timezone.utc) + timedelta(days=day_offset)


@pytest.fixture
def log_db(db, pg_test_dsn, monkeypatch):
    """A made-up query log: 10 questions on DAY and DAY+2, plus 1 the day before the period."""
    db.execute("DELETE FROM answer_ratings")
    db.execute("DELETE FROM query_log")
    user = db.execute("INSERT INTO users (email, password_hash, role) VALUES ('stats@test.com', 'x', 'learner') "
                      "ON CONFLICT (email) DO UPDATE SET role = 'learner' RETURNING id").fetchone()[0]
    rows = [  # (day, endpoint, query, outcome, latency, error, rewritten)
        (0, "chat", "four forces", "answered", 1000, None, None),
        (0, "chat", "and lift?", "answered", 2000, None, "what is lift?"),
        (0, "chat", "pitot tube", "low_confidence", 3000, None, None),
        (0, "chat", "best pizza in town", "no_answer", 400, None, None),
        (0, "answer", "carburetor icing", "answered", 5000, None, None),
        (2, "chat", "weather radar on a submarine", "no_answer", 600, None, None),
        (2, "chat", "stall speed", "error", 30000, "LLMFailure", None),
        (2, "search", "flaps", "answered", 200, None, None),
        (2, "chat", "altimeter", "answered", 1500, None, None),
        (2, "chat", "VOR", "answered", 2500, None, None),
        (-1, "chat", "before the period", "error", 100, "OSError", None),
    ]
    ids = {}
    for day, endpoint, query, outcome, latency, error, rewritten in rows:
        ids[query] = db.execute(
            "INSERT INTO query_log (asked_at, endpoint, query, outcome, latency_ms, error, rewritten_query) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (at(day), endpoint, query, outcome, latency, error, rewritten)).fetchone()[0]
    for query, rating in (("four forces", "good"), ("and lift?", "bad"), ("altimeter", "good"),
                          ("before the period", "bad")):
        db.execute("INSERT INTO answer_ratings (query_id, user_id, rating) VALUES (%s, %s, %s)",
                   (ids[query], user, rating))
    db.commit()
    monkeypatch.setattr(analytics, "DSN", pg_test_dsn)
    return ids


def test_volume_outcomes_and_failure_rate(log_db):
    s = analytics.summary(DAY, DAY + timedelta(days=2))
    assert s["period"] == {"start": "2026-11-10", "end": "2026-11-12", "days": 3}
    assert s["totals"] == {"questions": 10, "answered": 6, "low_confidence": 1, "no_answer": 2, "error": 1}
    assert s["failure_rate"] == 0.1          # FR-007: questions ending in an error / questions
    assert s["no_answer_rate"] == 0.2
    assert s["by_endpoint"] == {"answer": 1, "chat": 8, "search": 1}


def test_latency_leaves_out_the_failed_questions(log_db):
    s = analytics.summary(DAY, DAY + timedelta(days=2))
    # 9 questions that did not fail: 200 400 600 1000 1500 2000 2500 3000 5000
    assert s["latency_ms"]["p50"] == 1500
    assert s["latency_ms"]["max"] == 5000
    assert s["latency_ms"]["average"] == round((200 + 400 + 600 + 1000 + 1500 + 2000 + 2500 + 3000 + 5000) / 9)


def test_every_day_of_the_period_is_listed_even_without_questions(log_db):
    s = analytics.summary(DAY, DAY + timedelta(days=2))
    assert [(d["day"], d["questions"], d["no_answer"], d["errors"]) for d in s["per_day"]] == [
        ("2026-11-10", 5, 1, 0), ("2026-11-11", 0, 0, 0), ("2026-11-12", 5, 1, 1)]
    assert s["per_day"][1]["p50_ms"] is None


def test_unanswered_and_failed_questions_are_listed_newest_first(log_db):
    s = analytics.summary(DAY, DAY + timedelta(days=2))
    assert [q["query"] for q in s["unanswered"]] == ["weather radar on a submarine", "best pizza in town"]
    assert [(q["query"], q["error"]) for q in s["failed"]] == [("stall speed", "LLMFailure")]
    assert {"asked_at", "endpoint", "latency_ms", "top_score", "rewritten_query", "answer_mode"} <= set(s["unanswered"][0])


def test_ratings_and_bad_responses_of_the_period(log_db):
    s = analytics.summary(DAY, DAY + timedelta(days=2))
    assert s["ratings"] == {"good": 2, "bad": 1}       # the bad rating before the period is not counted
    [bad] = s["bad_responses"]
    assert bad["query"] == "and lift?" and bad["rewritten_query"] == "what is lift?"
    assert bad["rated_by"] == "stats@test.com"


def test_empty_period(log_db):
    s = analytics.summary(DAY + timedelta(days=30), DAY + timedelta(days=31))   # UC-09 A1
    assert s["totals"]["questions"] == 0
    assert s["failure_rate"] is None and s["no_answer_rate"] is None
    assert s["latency_ms"] == {"average": None, "p50": None, "p95": None, "max": None}
    assert s["unanswered"] == [] and s["bad_responses"] == []
    assert len(s["per_day"]) == 2
