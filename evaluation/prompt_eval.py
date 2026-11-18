"""Is the LLM system prompt reliable? (P7-26, supervisor request of 3 Nov; FR-002, BR-004)

Usage (from the repository root, database running, LLM_* settings in the environment or .env):
    python evaluation/prompt_eval.py <run_name> --prompt v1 [--runs 3] [--sleep 6] [--seed 7]

For every question of evaluation/questions.csv it does what GET /answer does:
    found  = retrieve(question, 5)
    answer = generate_answer(question, found["results"], found["reason"])
and repeats the answer step --runs times (retrieval is deterministic, so it is done once).
--prompt v2 reads backend/prompts/answer_system_v2.txt, so two prompts can be compared.

It writes evaluation/runs/<run_name>/:
    prompt_eval.csv    one row per (question, run)
    summary.md         the numbers below
    citation_check.csv 20 random kept sentences next to the passages they cite, for a hand check

A 429 or 5xx answer from the LLM server is retried up to 3 times (waits 10, 20, 40 s, or the
Retry-After header when there is one). The status code of the last answer and the number of retries
are written in each row. Only the code and the wait are ever printed: no key, no header value.

Counts per row:
    returned        sentences in the LLM's JSON
    kept            sentences that have a citation, cite only given ids, and pass the numeric guard
    numeric_dropped sentences with valid citations that the numeric guard still removed
The other drops (no citation or unknown id) are returned - kept - numeric_dropped.
The API key is never printed or written.
"""
import argparse
import csv
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))
from backend import answer, retrieval  # noqa: E402
from run_eval import QUESTIONS, RUNS, git_commit, read_csv  # noqa: E402

PROMPTS = ROOT / "backend" / "prompts"
TOP_K = 5
SAMPLE_SIZE = 20
ROW_FIELDS = ["question_id", "run", "mode", "returned", "kept", "numeric_dropped",
              "cited_ids", "answer_text", "fallback_reason", "http_status", "retries"]
MAX_RETRIES = 3
FIRST_WAIT = 10      # seconds; doubles at each retry
MAX_WAIT = 120       # also the cap for a Retry-After header
CHECK_FIELDS = ["question_id", "sentence", "cited_ids", "cited_passage_text", "supported (y/n)"]


class HttpLog:
    """What the last LLM call did on the wire: the last status code and the number of retries."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.status = ""
        self.retries = 0


def retry_after_seconds(response):
    """Seconds asked for by the Retry-After header, or None (missing, or a date, which is not used)."""
    try:
        seconds = float(response.headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None
    return min(max(seconds, 0.0), MAX_WAIT)


def retrying_post(real_post, log, sleep=time.sleep, say=lambda message: None):
    """httpx.post with up to MAX_RETRIES retries on 429 and 5xx. call_llm uses it unchanged.

    The retry is done here, below call_llm, so the request is exactly the one of GET /answer."""
    def post(*args, **kwargs):
        for attempt in range(MAX_RETRIES + 1):
            response = real_post(*args, **kwargs)
            code = response.status_code
            log.status = code
            if not (code == 429 or code >= 500) or attempt == MAX_RETRIES:
                return response
            wait = retry_after_seconds(response)
            if wait is None:
                wait = min(FIRST_WAIT * 2 ** attempt, MAX_WAIT)
            log.retries += 1
            say(f"  HTTP {code}: retry {attempt + 1} of {MAX_RETRIES} in {wait:g} s")
            sleep(wait)
    return post


def is_no_answer(question):
    return question["type"] == "no-answer"


def run_once(query, found, settings, llm=None, http=None):
    """One call of generate_answer, plus the counts it does not report.

    Returns (row without question_id/run, kept sentences). llm replaces call_llm in tests.
    http: the HttpLog that retrying_post fills; its status and retries go into the row."""
    llm = llm or answer.call_llm
    if http:
        http.reset()
    raw = []

    def spy(q, results, s):
        text = llm(q, results, s)
        raw.append(text)           # kept so the sentences the LLM returned can be counted
        return text

    out = answer.generate_answer(query, found["results"], found["reason"], llm=spy, settings=settings,
                                 confidence=found.get("confidence"))
    returned = kept = numeric_dropped = 0
    if raw:
        try:
            sentences = answer.parse_sentences(raw[0])
        except answer.LLMFailure:
            sentences = []
        given = {answer.passage_id(r) for r in found["results"]}
        well_cited = [s for s in sentences if s["text"] and s["citations"]
                      and all(c in given for c in set(s["citations"]))]
        kept = len(answer.keep_valid(sentences, found["results"]))
        returned = len(sentences)
        numeric_dropped = len(well_cited) - kept
    cited = sorted({c for s in out["sentences"] for c in s["citations"]})
    row = {"mode": out["mode"], "returned": returned, "kept": kept, "numeric_dropped": numeric_dropped,
           "cited_ids": ";".join(map(str, cited)),
           "answer_text": " ".join(s["text"] for s in out["sentences"]),
           "fallback_reason": out["fallback_reason"] or "",
           "http_status": http.status if http else "", "retries": http.retries if http else 0}
    return row, out["sentences"]


def summarize(rows, questions):
    """The numbers of the summary, as plain values (the tests check these).

    Share kept, numeric drops and stability use only the rows with mode llm: a fallback row
    (extractive) is not an answer of the LLM. Fallbacks are counted on their own."""
    no_answer_ids = {q["id"] for q in questions if is_no_answer(q)}
    llm_rows = [r for r in rows if r["mode"] == "llm"]
    returned = sum(int(r["returned"]) for r in llm_rows)
    kept = sum(int(r["kept"]) for r in llm_rows)
    na_rows = [r for r in rows if r["question_id"] in no_answer_ids]
    fallbacks = [r for r in rows if r["mode"] == "extractive"]
    empty_rows = [r for r in fallbacks if r["fallback_reason"] == "no_valid_sentences"]
    # stability: questions with at least 2 llm runs; stable = the same cited ids in all of them
    llm_by_question = {}
    for r in llm_rows:
        llm_by_question.setdefault(r["question_id"], []).append(r)
    comparable = {qid: rs for qid, rs in llm_by_question.items() if len(rs) >= 2}
    stable = [qid for qid, rs in comparable.items() if len({r["cited_ids"] for r in rs}) == 1]
    retried = [r for r in rows if int(r.get("retries") or 0) > 0]
    return {
        "rows": len(rows), "llm_runs": len(llm_rows), "returned": returned, "kept": kept,
        "share_kept": kept / returned if returned else None,
        "numeric_dropped": sum(int(r["numeric_dropped"]) for r in llm_rows),
        "modes": dict(Counter(r["mode"] for r in rows)),
        "no_answer_runs": len(na_rows),
        "correct_refusals": sum(1 for r in na_rows if r["mode"] == "no_answer"),
        # answerable questions that the LLM-refusal rule turned into "no answer" (answer.py rule 4)
        "answerable_refused_by_llm": sorted({r["question_id"] for r in rows
                                             if r["question_id"] not in no_answer_ids
                                             and r["fallback_reason"] == "llm_refused_low_confidence"}),
        "llm_said_nothing": sum(1 for r in na_rows if r in empty_rows and int(r["returned"]) == 0),
        "stable": len(stable), "stable_of": len(comparable),
        "unstable": sorted(set(comparable) - set(stable)),
        "one_llm_run_only": sorted(set(llm_by_question) - set(comparable)),
        "extractive": len(fallbacks),
        "fallback_reasons": dict(Counter(r["fallback_reason"] for r in fallbacks)),
        # the LLM answered but nothing survived: not in the share above, shown so it is not hidden
        "empty_after_checks_rows": len(empty_rows),
        "empty_after_checks_returned": sum(int(r["returned"]) for r in empty_rows),
        "http_errors": dict(Counter(str(r.get("http_status") or "none") for r in fallbacks
                                    if r["fallback_reason"] == "http_error")),
        "retried_calls": len(retried), "retries": sum(int(r["retries"]) for r in retried),
        "retried_recovered": sum(1 for r in retried if r["fallback_reason"] != "http_error"),
    }


def pick_sample(candidates, n=SAMPLE_SIZE, seed=7):
    """n candidates chosen with a seeded generator: the same seed gives the same sample."""
    return random.Random(seed).sample(candidates, min(n, len(candidates)))


def pct(a, b):
    return f"{a}/{b} = {a / b:.1%}" if b else f"{a}/{b} (n/a)"


def summary_text(name, prompt, s, meta):
    reasons = ", ".join(f"{k or '?'}: {v}" for k, v in sorted(s["fallback_reasons"].items())) or "none"
    codes = ", ".join(f"{k}: {v}" for k, v in sorted(s["http_errors"].items())) or "none"
    lines = [f"# Prompt evaluation `{name}` (prompt {prompt})", "",
             f"- Date (UTC): {meta.get('date', '?')}; git commit: {meta.get('commit', '?')}",
             f"- Rows (question x run): {s['rows']}; modes: {s['modes']}",
             f"- **Rows with mode llm: {s['llm_runs']}.** The first measures below use only these rows.", "",
             "| Measure | Result |", "| --- | --- |",
             f"| Sentences returned by the LLM (llm rows) | {s['returned']} |",
             f"| Sentences kept (cited, valid id, numbers ok) | {pct(s['kept'], s['returned'])} |",
             f"| Dropped by the numeric guard | {s['numeric_dropped']} |",
             f"| Dropped for a missing or unknown citation | {s['returned'] - s['kept'] - s['numeric_dropped']} |",
             f"| Stability (same cited ids in every llm run), questions with 2+ llm runs | "
             f"{pct(s['stable'], s['stable_of'])} |",
             f"| Correct refusals on no-answer questions (mode no_answer, per run) | "
             f"{pct(s['correct_refusals'], s['no_answer_runs'])} |",
             f"| No-answer runs where the LLM itself returned no sentence | {s['llm_said_nothing']} |",
             f"| Answerable questions turned into no answer by the LLM refusal (low confidence) | "
             f"{', '.join(s['answerable_refused_by_llm']) or 'none'} |", "",
             "Fallbacks (reported separately; they are not LLM answers):", "",
             "| Measure | Result |", "| --- | --- |",
             f"| Extractive fallbacks (rows) | {s['extractive']} ({reasons}) |",
             f"| http_error rows by last HTTP status | {codes} |",
             f"| LLM calls that needed a retry | {s['retried_calls']} ({s['retries']} retries in all; "
             f"{s['retried_recovered']} of these calls ended without http_error) |",
             f"| LLM answered but nothing survived the checks (no_valid_sentences) | "
             f"{s['empty_after_checks_rows']} rows, {s['empty_after_checks_returned']} sentences, all dropped; "
             f"not in the share above |", "",
             "Reading notes:",
             "- http_error / timeout / missing_api_key are server or setup problems, not the prompt. "
             "A run with many of them says little about the prompt.",
             "- Questions with fewer than 2 llm runs cannot be compared and are left out of stability: "
             + (", ".join(s["one_llm_run_only"]) or "none"),
             "- Unstable questions: " + (", ".join(s["unstable"]) or "none"), ""]
    return "\n".join(lines)


def write_csv(path, fields, rows, encoding="utf-8"):
    with open(path, "w", encoding=encoding, newline="") as fh:   # csv writes CRLF line endings
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(questions, retrieve_for, settings, runs, pause=lambda: None, llm=None, log=lambda m: None,
             http=None):
    """Ask every question `runs` times. Returns (rows, sentence candidates for the citation check).

    retrieve_for(question_text) -> what retrieve() returns. pause() is called after each LLM call."""
    rows, candidates = [], []
    for q in questions:
        found = retrieve_for(q["question"])
        texts = {answer.passage_id(r): answer.passage_text(r) for r in found["results"]}
        for run in range(1, runs + 1):
            row, sentences = run_once(q["question"], found, settings, llm, http)
            rows.append({"question_id": q["id"], "run": run, **row})
            if row["mode"] == "llm" and run == 1:
                for sentence in sentences:
                    candidates.append({
                        "question_id": q["id"], "sentence": sentence["text"],
                        "cited_ids": ";".join(map(str, sentence["citations"])),
                        "cited_passage_text": "\n---\n".join(f"[{c}] {texts[c]}" for c in sentence["citations"]),
                        "supported (y/n)": ""})
            log(f"{q['id']} run {run}: {row['mode']}"
                + (f" (HTTP {row['http_status']})" if row["fallback_reason"] == "http_error" else ""))
            if row["mode"] != "no_answer":       # retrieval refused: no LLM call, no need to wait
                pause()
    return rows, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run_name")
    parser.add_argument("--prompt", default="v1", help="v1 reads backend/prompts/answer_system_v1.txt")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=6.0, help="seconds after each LLM call (Groq limits)")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    for label in (args.run_name, args.prompt):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", label):
            sys.exit("run name and prompt: letters, digits, '.', '_' and '-' only")
    prompt_file = PROMPTS / f"answer_system_{args.prompt}.txt"
    if not prompt_file.is_file():
        sys.exit(f"{prompt_file} not found")
    folder = RUNS / args.run_name
    if (folder / "prompt_eval.csv").exists():
        sys.exit(f"{folder} already has a prompt_eval.csv: choose a new run name (runs are kept as evidence)")
    settings = answer.load_settings()
    missing = [name for name in answer.SETTINGS if not settings[name]]
    if missing:
        sys.exit("Missing LLM settings (names only): " + ", ".join(missing))

    answer.PROMPT_FILE = prompt_file          # call_llm reads this at every call
    questions = read_questions()
    index = retrieval.load_index()
    http, real_post = HttpLog(), httpx.post
    httpx.post = retrying_post(real_post, http, say=print)   # call_llm calls httpx.post
    try:
        rows, candidates = evaluate(
            questions, lambda text: retrieval.retrieve(text, TOP_K, index), settings, args.runs,
            pause=lambda: time.sleep(args.sleep), log=print, http=http)
    finally:
        httpx.post = real_post

    folder.mkdir(parents=True, exist_ok=True)
    write_csv(folder / "prompt_eval.csv", ROW_FIELDS, rows)
    write_csv(folder / "citation_check.csv", CHECK_FIELDS, pick_sample(candidates, SAMPLE_SIZE, args.seed),
              encoding="utf-8-sig")             # BOM: Excel reads the accents and quotes correctly
    meta = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "commit": git_commit()}
    text = summary_text(args.run_name, args.prompt, summarize(rows, questions), meta)
    with open(folder / "summary.md", "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)
    print(text)
    print(f"Saved to {folder}")


def read_questions():
    return read_csv(QUESTIONS)


if __name__ == "__main__":
    main()
