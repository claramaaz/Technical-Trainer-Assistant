import numpy as np

from backend.retrieval import Index, NO_ANSWER, THRESHOLD, retrieve

QUERY = np.array([1.0, 0.0])  # the "question" vector


def make_index(score):
    # One figure whose cosine similarity with QUERY is exactly `score`.
    vector = np.array([[score, (1 - score ** 2) ** 0.5]])
    doc = {
        "figure_number": "9-1",
        "caption": "Figure 9-1. Test figure",
        "image_path": "x.png",
        "passage": "Some text.",
        "printed_page": "9-4",
    }
    return Index([doc], vector, "Test Handbook")


def test_score_064_gives_no_answer():
    out = retrieve("q", index=make_index(0.64), query_vector=QUERY)
    assert out == {"results": [], "reason": NO_ANSWER}


def test_score_066_returns_figure_with_provenance():
    out = retrieve("q", index=make_index(0.66), query_vector=QUERY)
    result = out["results"][0]
    assert out["reason"] is None
    assert result["figure_id"] == "9-1"
    assert result["printed_page"] == "9-4"
    assert result["handbook"] == "Test Handbook"


def test_score_exactly_at_threshold_is_accepted():
    out = retrieve("q", index=make_index(THRESHOLD), query_vector=QUERY)
    assert out["reason"] is None
    assert out["results"][0]["figure_id"] == "9-1"
