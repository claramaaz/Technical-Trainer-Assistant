"""Tests for backend/retrieval.py.   Run from the repository root:   python -m pytest -q tests/test_retrieval.py

Three tests use the real index and the real model (the first run loads the model, a few seconds);
the boundary tests use a tiny made-up index so the expected scores are known exactly.
"""
import numpy as np
import pytest

from backend import retrieval
from backend.retrieval import Index, NO_ANSWER, THRESHOLD, retrieve

# Known questions with a wide margin (rank 1, top-1 score 0.868 / 0.911 / 0.840 in EVALUATION 3.2).
KNOWN = ["Q003", "Q021", "Q019"]


@pytest.mark.parametrize("qid", KNOWN)
def test_known_question_returns_expected_figure_first(qid, questions, real_index):
    q = questions[qid]
    out = retrieve(q["question"], k=5)
    assert out["reason"] is None
    top = out["results"][0]
    assert top["figure_id"] == q["figure_number"]
    assert top["printed_page"] == q["printed_page"]
    assert top["handbook"] == "Instrument Flying Handbook"
    assert top["caption"].startswith("Figure " + q["figure_number"])
    assert top["image_url"] == f"/figures/{q['figure_number']}/image"
    scores = [r["score"] for r in out["results"]]
    assert scores == sorted(scores, reverse=True) and len(scores) == 5


@pytest.mark.parametrize("qid", ["Q024", "Q025"])
def test_no_answer_questions_return_empty_with_reason(qid, questions, real_index):
    out = retrieve(questions[qid]["question"])
    assert out == {"results": [], "reason": NO_ANSWER}


def fake_index(*scores):
    """Documents whose cosine with the query [1, 0] is exactly the given scores."""
    vectors = np.array([[s, (1 - s * s) ** 0.5] for s in scores])
    docs = [{"figure_number": f"9-{i}", "caption": f"Figure 9-{i}. x", "image_path": "x.png",
             "passage": "p", "printed_page": f"9-{i}"} for i in range(len(scores))]
    return Index(docs, vectors, "Test Handbook")


def test_score_just_below_threshold_is_rejected():
    out = retrieve("q", index=fake_index(THRESHOLD - 0.001, 0.1), query_vector=np.array([1.0, 0.0]))
    assert out == {"results": [], "reason": NO_ANSWER}


def test_score_equal_to_threshold_is_accepted():
    out = retrieve("q", index=fake_index(THRESHOLD, 0.1), query_vector=np.array([1.0, 0.0]))
    assert out["reason"] is None and out["results"][0]["figure_id"] == "9-0"


def test_results_are_best_first_and_limited_to_k():
    idx = fake_index(0.2, 0.9, 0.7, 0.8)           # best first must be rows 1, 3, 2
    out = retrieve("q", k=3, index=idx, query_vector=np.array([1.0, 0.0]))
    assert [r["figure_id"] for r in out["results"]] == ["9-1", "9-3", "9-2"]


def test_threshold_decision_uses_best_score_not_first_row():
    # the best document is the last row; the rule must look at the best, not at row 0
    out = retrieve("q", index=fake_index(0.1, 0.2, 0.9), query_vector=np.array([1.0, 0.0]))
    assert out["reason"] is None and out["results"][0]["figure_id"] == "9-2"


def test_threshold_is_the_provisional_value():
    assert THRESHOLD == 0.65


def test_image_path_for_unknown_id_is_none(real_index):
    assert retrieval.image_path_for("../../etc/passwd") is None
    assert retrieval.image_path_for("99-99") is None


def test_image_file_that_exists_but_is_not_in_the_index_is_not_served(real_index, monkeypatch):
    # figures/3-9.png exists on disk, but if 3-9 is not in the index the id must not be served:
    # the path is taken from the index, never built from the URL.
    assert retrieval.image_path_for("3-9") is not None
    without = Index([d for d in real_index.documents if d["figure_number"] != "3-9"],
                    real_index.vectors, real_index.handbook)
    monkeypatch.setattr(retrieval, "load_index", lambda: without)
    assert retrieval.image_path_for("3-9") is None


def test_results_do_not_contain_the_server_file_path():
    # The browser only needs image_url; the path of the file on the server must not be sent.
    out = retrieve("q", index=fake_index(0.9, 0.8), query_vector=np.array([1.0, 0.0]))
    for r in out["results"]:
        assert "image_path" not in r
        assert "x.png" not in str(r)
        assert r["image_url"].startswith("/figures/")
