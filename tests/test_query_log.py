"""Tests for the query log (P7-28), written from FR-007 and UC-02:
"for every question asked: its time, its latency and its outcome (answered, no answer
found, or error)", and the list of unanswered questions must be readable.

Retrieval and the LLM are replaced by fakes, so these tests need no model and no Groq key.
They write only to the temporary test database (conftest.py), never to the real one.
Run from the repository root:   python -m pytest -q tests/test_query_log.py
"""
import time

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import query_log

client = TestClient(app_module.app, raise_server_exceptions=False)

TWO_RESULTS = {"results": [{"id": 55, "score": 0.81}, {"id": 7, "score": 0.70}], "reason": None}
NO_ANSWER = {"results": [], "reason": "no_adequate_answer"}


@pytest.fixture
def log_db(db, pg_test_dsn, monkeypatch):
    """Empty query_log in the temporary database; the app logs there."""
    db.execute("TRUNCATE query_log")
    db.commit()
    monkeypatch.setattr(query_log, "DSN", pg_test_dsn)
    monkeypatch.setattr(query_log, "ENABLED", True)
    return db


def rows(conn):
    conn.commit()  # new snapshot: see rows written by the app's own connection
    cur = conn.execute("SELECT endpoint, query, outcome, latency_ms, result_count, top_score,"
                       " answer_mode, error, asked_at FROM query_log ORDER BY id")
    names = [c.name for c in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def fake_retrieve(result):
    return lambda q, k: result


def test_answered_question_is_logged(log_db, monkeypatch):
    monkeypatch.setattr(app_module, "retrieve", fake_retrieve(TWO_RESULTS))
    before = time.time()
    assert client.get("/search", params={"q": "  four forces  "}).status_code == 200
    [row] = rows(log_db)
    assert row["endpoint"] == "search" and row["query"] == "four forces"
    assert row["outcome"] == "answered" and row["error"] is None
    assert row["result_count"] == 2 and row["top_score"] == pytest.approx(0.81, abs=1e-6)
    assert row["asked_at"].timestamp() >= before - 5  # the time of the question is recorded


def test_unanswered_question_is_logged_and_can_be_listed(log_db, monkeypatch):
    monkeypatch.setattr(app_module, "retrieve", fake_retrieve(NO_ANSWER))
    client.get("/search", params={"q": "how do I bake bread"})
    monkeypatch.setattr(app_module, "retrieve", fake_retrieve(TWO_RESULTS))
    client.get("/search", params={"q": "four forces"})
    log_db.commit()
    unanswered = [r[0] for r in log_db.execute("SELECT query FROM query_log WHERE outcome = 'no_answer'")]
    assert unanswered == ["how do I bake bread"]
    assert [r["result_count"] for r in rows(log_db)] == [0, 2]


def test_failure_is_logged_as_error(log_db, monkeypatch):
    def broken(q, k):
        raise RuntimeError("database gone")
    monkeypatch.setattr(app_module, "retrieve", broken)
    assert client.get("/search", params={"q": "inner ear"}).status_code == 500
    [row] = rows(log_db)
    assert row["outcome"] == "error" and row["error"] == "RuntimeError"
    # only the class name is stored, never the message (it could contain server details)
    assert "database gone" not in str(row)


def test_latency_is_the_real_time_taken(log_db, monkeypatch):
    def slow(q, k):
        time.sleep(0.12)
        return TWO_RESULTS
    monkeypatch.setattr(app_module, "retrieve", slow)
    client.get("/search", params={"q": "four forces"})
    [row] = rows(log_db)
    assert 120 <= row["latency_ms"] < 5000


def test_answer_endpoint_logs_the_answer_mode(log_db, monkeypatch):
    monkeypatch.setattr(app_module, "retrieve", fake_retrieve(TWO_RESULTS))
    monkeypatch.setattr(app_module, "generate_answer",
                        lambda q, results, reason: {"mode": "extractive", "sentences": [], "fallback_reason": "no_key"})
    assert client.get("/answer", params={"q": "four forces"}).status_code == 200
    [row] = rows(log_db)
    assert (row["endpoint"], row["outcome"], row["answer_mode"]) == ("answer", "answered", "extractive")


def test_failure_inside_answer_generation_is_logged(log_db, monkeypatch):
    monkeypatch.setattr(app_module, "retrieve", fake_retrieve(TWO_RESULTS))
    def broken(q, results, reason):
        raise ValueError("bad")
    monkeypatch.setattr(app_module, "generate_answer", broken)
    assert client.get("/answer", params={"q": "four forces"}).status_code == 500
    assert [(r["endpoint"], r["outcome"]) for r in rows(log_db)] == [("answer", "error")]


@pytest.mark.parametrize("q", ["", "   "])
def test_blank_query_is_not_a_question_and_is_not_logged(log_db, monkeypatch, q):
    monkeypatch.setattr(app_module, "retrieve", fake_retrieve(TWO_RESULTS))
    assert client.get("/search", params={"q": q}).status_code == 422
    assert rows(log_db) == []


def test_database_rejects_an_unknown_outcome(log_db):
    with pytest.raises(psycopg.errors.CheckViolation):
        log_db.execute("INSERT INTO query_log (endpoint, query, outcome, latency_ms)"
                       " VALUES ('search', 'x', 'maybe', 3)")
    log_db.rollback()


def test_log_failure_does_not_break_the_search(monkeypatch):
    # No database needed: the log points to a closed port.
    monkeypatch.setattr(query_log, "DSN", "host=127.0.0.1 port=1 dbname=x user=x connect_timeout=2")
    monkeypatch.setattr(query_log, "ENABLED", True)
    monkeypatch.setattr(app_module, "retrieve", fake_retrieve(TWO_RESULTS))
    r = client.get("/search", params={"q": "four forces"})
    assert r.status_code == 200 and r.json() == TWO_RESULTS
