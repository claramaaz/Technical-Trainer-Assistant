"""Tests for the low-confidence match (P7-48), written from SPEC FR-002 ("match, low-confidence
match or no match"), UC-02 A3 and FR-007 (low confidence is its own logged outcome).

Fake index with fixed scores: no model; the logging test uses the temporary test database.
Run:   python -m pytest -q tests/test_low_confidence.py
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import query_log, retrieval
from backend.retrieval import LOW_CONFIDENCE_BELOW, NO_ANSWER, THRESHOLD, retrieve
from fake_index import make_fake


def index_with_best_score(score):
    docs = [{"figure_number": "1-1", "caption": "Figure 1-1.", "image_path": None, "passage": "",
             "printed_page": "1-1"}]
    return make_fake(docs, np.array([[score, 0.0]]))


def ask(score):
    return retrieve("anything", k=1, index=index_with_best_score(score), query_vector=np.array([1.0, 0.0]))


def test_the_zones_are_in_order():
    assert THRESHOLD < LOW_CONFIDENCE_BELOW < 1


@pytest.mark.parametrize("score, confidence", [
    (THRESHOLD, "low"),                      # lowest score that is still answered
    (LOW_CONFIDENCE_BELOW - 0.001, "low"),
    (LOW_CONFIDENCE_BELOW, "high"),
    (0.95, "high"),
])
def test_answered_results_carry_their_confidence(score, confidence):
    out = ask(score)
    assert out["reason"] is None and len(out["results"]) == 1
    assert out["confidence"] == confidence


def test_no_answer_is_unchanged():
    assert ask(THRESHOLD - 0.001) == {"results": [], "reason": NO_ANSWER}


def test_outcome_names():
    assert query_log.outcome_of({"results": [{}], "reason": None, "confidence": "low"}) == "low_confidence"
    assert query_log.outcome_of({"results": [{}], "reason": None, "confidence": "high"}) == "answered"
    assert query_log.outcome_of({"results": [], "reason": NO_ANSWER}) == "no_answer"


def test_low_confidence_is_logged_as_its_own_outcome(db, pg_test_dsn, monkeypatch):
    db.execute("TRUNCATE query_log")
    db.commit()
    monkeypatch.setattr(query_log, "DSN", pg_test_dsn)
    monkeypatch.setattr(query_log, "ENABLED", True)
    monkeypatch.setattr(app_module, "retrieve", lambda q, k: ask(THRESHOLD + 0.01))
    r = TestClient(app_module.app).get("/search", params={"q": "something vague"})
    assert r.status_code == 200 and r.json()["confidence"] == "low"
    db.commit()
    assert db.execute("SELECT outcome FROM query_log").fetchall() == [("low_confidence",)]


def test_answer_route_also_gives_the_confidence(monkeypatch):
    monkeypatch.setattr(app_module, "retrieve", lambda q, k: ask(THRESHOLD + 0.01))
    monkeypatch.setattr(app_module, "generate_answer",
                        lambda q, results, reason, **kw: {"mode": "extractive", "sentences": [], "fallback_reason": "test"})
    assert TestClient(app_module.app).get("/answer", params={"q": "x"}).json()["confidence"] == "low"
