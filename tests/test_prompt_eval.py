"""Tests of evaluation/prompt_eval.py (P7-26) with a FAKE LLM: no network, no database, no key."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))

import prompt_eval as pe  # noqa: E402
from backend import answer  # noqa: E402

SETTINGS = {"LLM_PROVIDER": "x", "LLM_BASE_URL": "http://fake", "LLM_MODEL": "m", "LLM_API_KEY": "secret-test-key"}

FOUND = {"reason": None, "results": [
    {"id": 748, "caption": "Figure 3-1. The four forces.",
     "passage": "Lift opposes weight. Thrust is about 1,000 pounds in this example."},
    {"id": 55, "caption": "Figure 4-3.", "passage": "The four basic forces are lift, weight, thrust, and drag."},
]}
NO_ANSWER = {"results": [], "reason": answer.NO_ANSWER}

QUESTIONS = [
    {"id": "Q1", "question": "four forces", "type": "topic"},
    {"id": "Q2", "question": "boeing capacity", "type": "no-answer"},
]


def fake(*pairs):
    payload = {"sentences": [{"text": t, "citations": c} for t, c in pairs]}
    return lambda query, results, settings: json.dumps(payload)


def once(llm, found=FOUND):
    return pe.run_once("q", found, SETTINGS, llm)


def test_counts_for_a_mixed_answer():
    row, sentences = once(fake(
        ("Lift opposes weight. [748]", [748]),          # kept
        ("Thrust is 5000 pounds. [748]", [748]),        # numeric guard
        ("Drag is a force.", []),                       # no citation
        ("Something. [999]", [999]),                    # unknown id
    ))
    assert (row["mode"], row["returned"], row["kept"], row["numeric_dropped"]) == ("llm", 4, 1, 1)
    assert row["cited_ids"] == "748" and row["answer_text"] == "Lift opposes weight. [748]"
    assert len(sentences) == 1


def test_comma_number_is_not_a_numeric_drop():
    row, _ = once(fake(("Thrust is 1000 pounds. [748]", [748])))
    assert (row["kept"], row["numeric_dropped"]) == (1, 0)


def test_nothing_survives_gives_extractive_with_counts():
    row, _ = once(fake(("Thrust is 5000 pounds. [748]", [748])))
    assert row["mode"] == "extractive" and row["fallback_reason"] == "no_valid_sentences"
    assert (row["returned"], row["kept"], row["numeric_dropped"]) == (1, 0, 1)
    assert row["cited_ids"] == "55;748"    # the extractive answer cites the retrieved passages


def test_llm_failure_is_an_extractive_row_with_zero_counts():
    def broken(query, results, settings):
        raise answer.LLMFailure("http_error")
    row, _ = once(broken)
    assert (row["mode"], row["fallback_reason"], row["returned"]) == ("extractive", "http_error", 0)


def test_retrieval_refusal_never_calls_the_llm():
    def must_not_run(*args):
        raise AssertionError("LLM called")
    row, _ = once(must_not_run, NO_ANSWER)
    assert row["mode"] == "no_answer" and row["returned"] == 0


def row(qid, run, mode="llm", returned=2, kept=2, dropped=0, cited="748", reason=""):
    return {"question_id": qid, "run": run, "mode": mode, "returned": returned, "kept": kept,
            "numeric_dropped": dropped, "cited_ids": cited, "answer_text": "", "fallback_reason": reason}


def test_summary_numbers():
    rows = [
        row("Q1", 1, returned=4, kept=3, dropped=1), row("Q1", 2, returned=4, kept=4),
        row("Q1", 3, returned=2, kept=1, dropped=1, cited="55"),                        # different ids: unstable
        row("Q2", 1, mode="no_answer", returned=0, kept=0, cited=""),
        row("Q2", 2, mode="no_answer", returned=0, kept=0, cited=""),
        row("Q2", 3, mode="extractive", returned=0, kept=0, cited="55", reason="no_valid_sentences"),
        row("Q3", 1, mode="extractive", returned=0, kept=0, reason="http_error"),
    ]
    s = pe.summarize(rows, QUESTIONS)
    assert (s["returned"], s["kept"], s["numeric_dropped"]) == (10, 8, 2)
    assert s["share_kept"] == 0.8
    assert (s["correct_refusals"], s["no_answer_runs"], s["llm_said_nothing"]) == (2, 3, 1)
    assert s["unstable"] == ["Q1", "Q2"] and (s["stable"], s["stable_of"]) == (1, 3)   # only Q3 is stable
    assert s["extractive"] == 2 and s["fallback_reasons"] == {"no_valid_sentences": 1, "http_error": 1}


def test_question_refused_by_retrieval_is_not_in_the_stability_count():
    rows = [row("Q2", r, mode="no_answer", returned=0, kept=0, cited="") for r in (1, 2, 3)]
    s = pe.summarize(rows, QUESTIONS)
    assert s["stable_of"] == 0 and s["correct_refusals"] == 3 and s["share_kept"] is None


def test_evaluate_runs_each_question_and_pauses_only_after_llm_calls():
    pauses = []
    rows, candidates = pe.evaluate(
        QUESTIONS, lambda text: NO_ANSWER if text == "boeing capacity" else FOUND, SETTINGS, 3,
        pause=lambda: pauses.append(1), llm=fake(("Lift opposes weight. [748]", [748])))
    assert len(rows) == 6 and [r["run"] for r in rows[:3]] == [1, 2, 3]
    assert len(pauses) == 3                       # the 3 runs of Q1 only
    assert len(candidates) == 1                   # run 1 of Q1 only
    assert "[748] Figure 3-1. The four forces. Lift opposes weight." in candidates[0]["cited_passage_text"]
    assert candidates[0]["supported (y/n)"] == ""


def test_sample_is_seeded_and_never_bigger_than_the_candidates():
    items = list(range(100))
    assert pe.pick_sample(items, 20, 7) == pe.pick_sample(items, 20, 7)
    assert pe.pick_sample(items, 20, 7) != pe.pick_sample(items, 20, 8)
    assert len(pe.pick_sample(items, 20, 7)) == 20 and len(pe.pick_sample([1, 2], 20, 7)) == 2


def test_summary_text_has_the_measures_and_no_key():
    s = pe.summarize([row("Q1", 1)], QUESTIONS)
    text = pe.summary_text("t", "v1", s, {"date": "d", "commit": "c"})
    assert "Stability" in text and "numeric guard" in text and "secret" not in text
