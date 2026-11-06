"""Tests for evaluation/run_eval.py (P7-17), written from SPEC 5.3 and brief section 8.

No database and no model: a fake index with two handbooks that BOTH have a figure "3-1"
(the trap of P7-25), and fixed question vectors. Run:   python -m pytest -q tests/test_run_eval.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))
import run_eval  # noqa: E402
from fake_index import make_fake  # noqa: E402


def doc(handbook_id, number, page):
    return {"figure_number": number, "caption": f"Figure {number}.", "image_path": None, "passage": "",
            "printed_page": page, "handbook_id": handbook_id, "handbook": handbook_id}


@pytest.fixture
def index():
    # db id 0: HB-A 3-1, 1: HB-B 3-1, 2: HB-A 4-2
    return make_fake([doc("HB-A", "3-1", "3-3"), doc("HB-B", "3-1", "3-7"), doc("HB-A", "4-2", "4-5")],
                     np.array([[0.8, 0.0], [0.9, 0.1], [0.1, 0.9]]))


QUESTIONS = [
    # Q1 expects HB-A 3-1. Over both handbooks, HB-B 3-1 scores higher (0.90 vs 0.80).
    {"id": "Q1", "question": "q1", "type": "topic", "handbook": "HB-A", "figure_number": "3-1"},
    # Q2 has no answer: best score 0.45, under the 0.65 threshold.
    {"id": "Q2", "question": "q2", "type": "no-answer", "handbook": "HB-A", "figure_number": ""},
    # Q3 expects HB-A 4-2 and finds it first, but with 0.54 < 0.65: refused by the threshold.
    {"id": "Q3", "question": "q3", "type": "symptom", "handbook": "HB-A", "figure_number": "4-2"},
]
VECTORS = {"q1": np.array([1.0, 0.0]), "q2": np.array([0.0, 0.5]), "q3": np.array([0.0, 0.6])}


@pytest.fixture
def rows(index):
    return run_eval.run_questions(QUESTIONS, index, embed=VECTORS.__getitem__, k=3)


def ranks(rows, qid, scope):
    return [(r["handbook_id"], r["figure_number"]) for r in rows if r["question_id"] == qid and r["scope"] == scope]


def test_same_figure_number_in_another_handbook_is_not_the_expected_figure(rows):
    assert ranks(rows, "Q1", "all")[:2] == [("HB-B", "3-1"), ("HB-A", "3-1")]
    expected = [r["rank"] for r in rows if r["question_id"] == "Q1" and r["scope"] == "all" and r["expected"]]
    assert expected == [2]


def test_own_scope_searches_only_the_question_handbook(rows):
    assert {h for h, _ in ranks(rows, "Q1", "own")} == {"HB-A"}
    assert {h for h, _ in ranks(rows, "Q1", "all")} == {"HB-A", "HB-B"}


def test_auto_metrics_no_answer_accuracy_and_refusals(rows):
    result = run_eval.evaluate_run(rows, QUESTIONS, scores={})
    own, all_ = result["own"], result["all"]
    assert own["auto_ranks"] == {"Q1": 1, "Q3": 1}
    assert all_["auto_ranks"] == {"Q1": 2, "Q3": 1}
    assert all_["auto"]["Hit@1"] == 0.5 and all_["auto"]["MRR@5"] == pytest.approx((1 / 2 + 1) / 2)
    # the threshold: the no-answer question is refused (correct), Q3 is refused although its figure is first
    assert all_["no_answer_correct"] == 1 and all_["no_answer"] == 1
    assert all_["false_refusals"] == ["Q3"]


def test_new_pairs_are_added_expected_prefilled_and_judged_scores_kept(rows):
    existing = [{"question_id": "Q1", "handbook_id": "HB-B", "figure_number": "3-1",
                 "score": "2", "judge": "Clara", "note": "same diagram, other handbook"}]
    merged = run_eval.merge_judgements(existing, rows)
    by_key = {run_eval.key(r): r for r in merged}
    assert by_key[("Q1", "HB-B", "3-1")]["judge"] == "Clara"            # a person's score is never touched
    assert by_key[("Q1", "HB-A", "3-1")]["score"] == "2"                # expected figure = 2 (SPEC 5.3)
    assert by_key[("Q1", "HB-A", "4-2")]["score"] == ""                 # left for a person
    assert not any(r["question_id"] == "Q2" for r in merged)            # no-answer questions are not judged
    assert len(merged) == len(by_key)                                   # each pair once, although in both scopes
    assert run_eval.merge_judgements(merged, rows) == merged            # running again adds nothing


def test_human_metrics_only_on_fully_judged_questions(rows):
    scores = {("Q1", "HB-B", "3-1"): 2, ("Q1", "HB-A", "3-1"): 2, ("Q1", "HB-A", "4-2"): 0,
              ("Q3", "HB-A", "4-2"): 2}                                  # Q3 still has unjudged figures
    result = run_eval.evaluate_run(rows, QUESTIONS, scores)["all"]
    assert result["human_judged"] == 1
    assert result["human_ranks"] == {"Q1": 1}   # judged equally correct: a human hit at rank 1, auto rank 2
    assert result["human"]["Hit@1"] == 1.0


@pytest.mark.parametrize("bad", ["3", "yes", "-1"])
def test_a_bad_score_stops_the_run(bad):
    with pytest.raises(ValueError):
        run_eval.scores_from([{"question_id": "Q1", "handbook_id": "HB-A", "figure_number": "3-1", "score": bad}])


def test_summary_shows_both_scopes_and_the_refusal(rows):
    result = run_eval.evaluate_run(rows, QUESTIONS, scores={})
    text = run_eval.summary_text("test", result, QUESTIONS, {"date": "d", "commit": "c"})
    assert "| own | auto (expected figure) | 2 |" in text and "| all | auto (expected figure) | 2 |" in text
    assert "1/2: Q3" in text and "| all | 1/1 |" in text
