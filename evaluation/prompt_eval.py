"""Is the LLM system prompt reliable? (P7-26, supervisor request of 3 Nov; FR-002, BR-004)

Usage (from the repository root, database running, LLM_* settings in the environment or .env):
    python evaluation/prompt_eval.py <run_name> --prompt v1 [--runs 3] [--sleep 2.5] [--seed 7]

For every question of evaluation/questions.csv it does what GET /answer does:
    found  = retrieve(question, 5)
    answer = generate_answer(question, found["results"], found["reason"])
and repeats the answer step --runs times (retrieval is deterministic, so it is done once).
--prompt v2 reads backend/prompts/answer_system_v2.txt, so two prompts can be compared.

It writes evaluation/runs/<run_name>/:
    prompt_eval.csv    one row per (question, run)
    summary.md         the numbers below
    citation_check.csv 20 random kept sentences next to the passages they cite, for a hand check

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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))
from backend import answer, retrieval  # noqa: E402
from run_eval import QUESTIONS, RUNS, git_commit, read_csv  # noqa: E402

PROMPTS = ROOT / "backend" / "prompts"
TOP_K = 5
SAMPLE_SIZE = 20
ROW_FIELDS = ["question_id", "run", "mode", "returned", "kept", "numeric_dropped",
              "cited_ids", "answer_text", "fallback_reason"]
CHECK_FIELDS = ["question_id", "sentence", "cited_ids", "cited_passage_text", "supported (y/n)"]


def is_no_answer(question):
    return question["type"] == "no-answer"


def run_once(query, found, settings, llm=None):
    """One call of generate_answer, plus the counts it does not report.

    Returns (row without question_id/run, kept sentences). llm replaces call_llm in tests."""
    llm = llm or answer.call_llm
    raw = []

    def spy(q, results, s):
        text = llm(q, results, s)
        raw.append(text)           # kept so the sentences the LLM returned can be counted
        return text

    out = answer.generate_answer(query, found["results"], found["reason"], llm=spy, settings=settings)
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
           "fallback_reason": out["fallback_reason"] or ""}
    return row, out["sentences"]


def summarize(rows, questions):
    """The numbers of the summary, as plain values (the tests check these)."""
    no_answer_ids = {q["id"] for q in questions if is_no_answer(q)}
    returned = sum(int(r["returned"]) for r in rows)
    kept = sum(int(r["kept"]) for r in rows)
    na_rows = [r for r in rows if r["question_id"] in no_answer_ids]
    by_question = {}
    for r in rows:
        by_question.setdefault(r["question_id"], []).append(r)
    # stable = the same cited ids in every run; questions refused by retrieval are not counted
    asked = {qid: rs for qid, rs in by_question.items() if any(r["mode"] != "no_answer" for r in rs)}
    stable = [qid for qid, rs in asked.items() if len({r["cited_ids"] for r in rs}) == 1]
    fallbacks = [r for r in rows if r["mode"] == "extractive"]
    return {
        "rows": len(rows), "returned": returned, "kept": kept,
        "share_kept": kept / returned if returned else None,
        "numeric_dropped": sum(int(r["numeric_dropped"]) for r in rows),
        "modes": dict(Counter(r["mode"] for r in rows)),
        "no_answer_runs": len(na_rows),
        "correct_refusals": sum(1 for r in na_rows if r["mode"] == "no_answer"),
        "llm_said_nothing": sum(1 for r in na_rows if r["mode"] == "extractive" and int(r["returned"]) == 0
                                and r["fallback_reason"] == "no_valid_sentences"),
        "stable": len(stable), "stable_of": len(asked),
        "unstable": sorted(set(asked) - set(stable)),
        "extractive": len(fallbacks),
        "fallback_reasons": dict(Counter(r["fallback_reason"] for r in fallbacks)),
    }


def pick_sample(candidates, n=SAMPLE_SIZE, seed=7):
    """n candidates chosen with a seeded generator: the same seed gives the same sample."""
    return random.Random(seed).sample(candidates, min(n, len(candidates)))


def pct(a, b):
    return f"{a}/{b} = {a / b:.1%}" if b else f"{a}/{b} (n/a)"


def summary_text(name, prompt, s, meta):
    reasons = ", ".join(f"{k or '?'}: {v}" for k, v in sorted(s["fallback_reasons"].items())) or "none"
    lines = [f"# Prompt evaluation `{name}` (prompt {prompt})", "",
             f"- Date (UTC): {meta.get('date', '?')}; git commit: {meta.get('commit', '?')}",
             f"- Rows (question x run): {s['rows']}; modes: {s['modes']}", "",
             "| Measure | Result |", "| --- | --- |",
             f"| Sentences returned by the LLM | {s['returned']} |",
             f"| Sentences kept (cited, valid id, numbers ok) | {pct(s['kept'], s['returned'])} |",
             f"| Dropped by the numeric guard | {s['numeric_dropped']} |",
             f"| Dropped for a missing or unknown citation | {s['returned'] - s['kept'] - s['numeric_dropped']} |",
             f"| Correct refusals on no-answer questions (mode no_answer, per run) | "
             f"{pct(s['correct_refusals'], s['no_answer_runs'])} |",
             f"| No-answer runs where the LLM itself returned no sentence | {s['llm_said_nothing']} |",
             f"| Stability (same cited ids in every run) | {pct(s['stable'], s['stable_of'])} |",
             f"| Extractive fallbacks (rows) | {s['extractive']} ({reasons}) |", "",
             "Reading notes:",
             "- Extractive fallbacks with reason http_error / timeout / missing_api_key are LLM or Groq problems; "
             "no_valid_sentences means the LLM answered but nothing survived the checks.",
             "- Stability counts questions that were sent to the LLM; questions refused by retrieval are left out.",
             "- Unstable questions: " + (", ".join(s["unstable"]) or "none"), ""]
    return "\n".join(lines)


def write_csv(path, fields, rows, encoding="utf-8"):
    with open(path, "w", encoding=encoding, newline="") as fh:   # csv writes CRLF line endings
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate(questions, retrieve_for, settings, runs, pause=lambda: None, llm=None, log=lambda m: None):
    """Ask every question `runs` times. Returns (rows, sentence candidates for the citation check).

    retrieve_for(question_text) -> what retrieve() returns. pause() is called after each LLM call."""
    rows, candidates = [], []
    for q in questions:
        found = retrieve_for(q["question"])
        texts = {answer.passage_id(r): answer.passage_text(r) for r in found["results"]}
        for run in range(1, runs + 1):
            row, sentences = run_once(q["question"], found, settings, llm)
            rows.append({"question_id": q["id"], "run": run, **row})
            if row["mode"] == "llm" and run == 1:
                for sentence in sentences:
                    candidates.append({
                        "question_id": q["id"], "sentence": sentence["text"],
                        "cited_ids": ";".join(map(str, sentence["citations"])),
                        "cited_passage_text": "\n---\n".join(f"[{c}] {texts[c]}" for c in sentence["citations"]),
                        "supported (y/n)": ""})
            log(f"{q['id']} run {run}: {row['mode']}")
            if row["mode"] != "no_answer":       # retrieval refused: no LLM call, no need to wait
                pause()
    return rows, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("run_name")
    parser.add_argument("--prompt", default="v1", help="v1 reads backend/prompts/answer_system_v1.txt")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=2.5, help="seconds after each LLM call (Groq limits)")
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
    rows, candidates = evaluate(
        questions, lambda text: retrieval.retrieve(text, TOP_K, index), settings, args.runs,
        pause=lambda: time.sleep(args.sleep), log=print)

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
