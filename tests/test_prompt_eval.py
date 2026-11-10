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


def row(qid, run, mode="llm", returned=2, kept=2, dropped=0, cited="748", reason="", status="", retries=0):
    return {"question_id": qid, "run": run, "mode": mode, "returned": returned, "kept": kept,
            "numeric_dropped": dropped, "cited_ids": cited, "answer_text": "", "fallback_reason": reason,
            "http_status": status, "retries": retries}


def test_share_and_stability_use_only_llm_rows():
    rows = [
        row("Q1", 1, returned=4, kept=3, dropped=1), row("Q1", 2, returned=4, kept=4),
        row("Q1", 3, mode="extractive", returned=0, kept=0, cited="55", reason="http_error", status=429),
        row("Q4", 1, returned=2, kept=1, dropped=1, cited="748"),
        row("Q4", 2, returned=2, kept=1, dropped=1, cited="55"),                       # different ids: unstable
        row("Q5", 1, returned=1, kept=1),
        row("Q5", 2, mode="extractive", returned=0, kept=0, reason="http_error", status=500),  # only 1 llm run
    ]
    s = pe.summarize(rows, QUESTIONS)
    assert s["llm_runs"] == 5
    assert (s["returned"], s["kept"], s["numeric_dropped"]) == (13, 10, 3)
    assert s["share_kept"] == 10 / 13
    assert (s["stable"], s["stable_of"], s["unstable"]) == (1, 2, ["Q4"])
    assert s["one_llm_run_only"] == ["Q5"]
    assert s["extractive"] == 2 and s["fallback_reasons"] == {"http_error": 2}


def test_fallback_rows_do_not_change_the_share():
    ok = [row("Q1", 1, returned=4, kept=2, dropped=2)]
    with_errors = ok + [row("Q1", r, mode="extractive", returned=0, kept=0, reason="http_error", status=429)
                        for r in (2, 3)]
    assert pe.summarize(ok, QUESTIONS)["share_kept"] == pe.summarize(with_errors, QUESTIONS)["share_kept"] == 0.5


def test_no_valid_sentences_are_reported_apart_from_the_share():
    rows = [row("Q1", 1, returned=2, kept=2),
            row("Q1", 2, mode="extractive", returned=3, kept=0, dropped=3, reason="no_valid_sentences")]
    s = pe.summarize(rows, QUESTIONS)
    assert s["share_kept"] == 1.0                      # the llm rows only
    assert (s["empty_after_checks_rows"], s["empty_after_checks_returned"]) == (1, 3)


def test_refusals_and_llm_said_nothing():
    rows = [
        row("Q2", 1, mode="no_answer", returned=0, kept=0, cited=""),
        row("Q2", 2, mode="no_answer", returned=0, kept=0, cited=""),
        row("Q2", 3, mode="extractive", returned=0, kept=0, cited="55", reason="no_valid_sentences"),
    ]
    s = pe.summarize(rows, QUESTIONS)
    assert (s["correct_refusals"], s["no_answer_runs"], s["llm_said_nothing"]) == (2, 3, 1)
    assert s["stable_of"] == 0 and s["share_kept"] is None   # no llm row at all


def test_http_errors_are_counted_by_status_and_retries_are_reported():
    rows = [
        row("Q1", 1, mode="extractive", returned=0, kept=0, reason="http_error", status=429, retries=3),
        row("Q1", 2, mode="extractive", returned=0, kept=0, reason="http_error", status=429, retries=3),
        row("Q1", 3, mode="extractive", returned=0, kept=0, reason="http_error", status=503, retries=3),
        row("Q4", 1, retries=1, status=200),                                     # recovered after one retry
        row("Q4", 2, status=200),
        row("Q5", 1, mode="extractive", returned=0, kept=0, reason="timeout"),
    ]
    s = pe.summarize(rows, QUESTIONS)
    assert s["http_errors"] == {"429": 2, "503": 1}
    assert (s["retried_calls"], s["retries"], s["retried_recovered"]) == (4, 10, 1)
    text = pe.summary_text("t", "v1", s, {})
    assert "429: 2" in text and "503: 1" in text and "Rows with mode llm: 2" in text


# --- retry on 429 and 5xx -------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status, headers=None):
        self.status_code, self.headers = status, headers or {}


def poster(*responses):
    """A fake httpx.post that returns these responses in turn (and counts the calls)."""
    queue, calls = list(responses), []

    def post(*args, **kwargs):
        calls.append(1)
        return queue.pop(0)
    post.calls = calls
    return post


def test_retry_after_429_then_success():
    log, waits = pe.HttpLog(), []
    post = pe.retrying_post(poster(FakeResponse(429), FakeResponse(200)), log, sleep=waits.append)
    assert post("url").status_code == 200
    assert (log.status, log.retries, waits) == (200, 1, [10])


def test_wait_grows_and_stops_after_three_retries():
    log, waits = pe.HttpLog(), []
    fake_post = poster(*[FakeResponse(503) for _ in range(10)])
    response = pe.retrying_post(fake_post, log, sleep=waits.append)("url")
    assert response.status_code == 503                 # call_llm then turns it into http_error
    assert len(fake_post.calls) == 4 and waits == [10, 20, 40]
    assert (log.status, log.retries) == (503, 3)


def test_retry_after_header_is_used_and_capped():
    log, waits = pe.HttpLog(), []
    fake_post = poster(FakeResponse(429, {"Retry-After": "7"}), FakeResponse(429, {"Retry-After": "9999"}),
                       FakeResponse(429, {"Retry-After": "not a number"}), FakeResponse(200))
    pe.retrying_post(fake_post, log, sleep=waits.append)("url")
    assert waits == [7, pe.MAX_WAIT, 40]               # bad value: back to the growing wait of that attempt


def test_other_errors_are_not_retried():
    for code in (400, 401, 404):
        log, waits = pe.HttpLog(), []
        fake_post = poster(FakeResponse(code))
        assert pe.retrying_post(fake_post, log, sleep=waits.append)("url").status_code == code
        assert waits == [] and log.retries == 0 and log.status == code


def test_run_once_puts_status_and_retries_in_the_row_and_resets_between_calls():
    log = pe.HttpLog()

    def llm_after_retry(query, results, settings):
        log.status, log.retries = 200, 2                # what retrying_post would have recorded
        return json.dumps({"sentences": [{"text": "Lift opposes weight. [748]", "citations": [748]}]})
    first, _ = pe.run_once("q", FOUND, SETTINGS, llm_after_retry, log)
    assert (first["http_status"], first["retries"]) == (200, 2)
    refused, _ = pe.run_once("q", NO_ANSWER, SETTINGS, llm_after_retry, log)   # no call: nothing carried over
    assert (refused["http_status"], refused["retries"]) == ("", 0)
