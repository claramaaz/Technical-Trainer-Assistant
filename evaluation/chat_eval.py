"""Evaluation of the chat (P7-55; supervisor meeting of 13 Nov 2026: cumulative chat with follow-ups).

Usage (from the repository root, database running, LLM and embedding keys in .env):
    python evaluation/chat_eval.py run <label>        # part A then part B
    python evaluation/chat_eval.py run <label> A      # only part A (the 50 questions)
    python evaluation/chat_eval.py run <label> B      # only part B (the 10 follow-up pairs)

Part A - the 50 questions of evaluation/questions.csv, each as the FIRST message of a new chat
         (POST /chat logic, backend/chat.py): answer mode, figures, whether the first figure shown is the
         expected one, both in the score order of retrieval and in the order shown by the chat (figures
         cited by the answer first), and whether the 8 no-answer questions get "no answer".
Part B - evaluation/chat_followups.csv: 10 pairs "first question -> follow-up with a pronoun". The
         follow-up's expected figure is the expected figure of an existing question of the 50 (column
         source_question). Each follow-up is asked twice:
           with history    = the real chat: first answer in the history, follow-up rewritten (backend/chat.py)
           without history = the follow-up searched alone, as a search box would do
         The difference shows what the cumulative chat brings. The rewritten question is saved for a
         person to check (column "check": faithful / changed).
Writes evaluation/runs/<label>/chat_single.csv, chat_followups.csv and summary.md.
About 80 LLM calls. Groq free tier for gpt-oss-120b: 8,000 tokens per minute and 200,000 per day; one
chat answer is about 2,500 tokens, so PAUSE_SECONDS = 20 (3 answers a minute) and parts A and B can be
run on different days. A question whose search or LLM fails is recorded as "error" and the run goes on.
"""
import csv
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import retrieval  # noqa: E402
from backend.chat import chat_turn  # noqa: E402

RUNS = ROOT / "evaluation" / "runs"
QUESTIONS = ROOT / "evaluation" / "questions.csv"
FOLLOWUPS = ROOT / "evaluation" / "chat_followups.csv"
PAUSE_SECONDS = 20
K = 5


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def rank_of(results, handbook, figure):
    """1-based position of the expected figure in a list of results, or None."""
    for i, r in enumerate(results, start=1):
        if r.get("handbook_id") == handbook and r.get("figure_id") == figure:
            return i
    return None


def by_score(results):
    return sorted(results, key=lambda r: -r.get("score", 0))


def history_of(message, turn):
    """The history the page would send after one turn: the question and the answer text."""
    answer = " ".join(s["text"] for s in turn["answer"]["sentences"])
    return [{"role": "user", "content": message}] + ([{"role": "assistant", "content": answer}] if answer else [])


def single_row(q, turn, ms):
    results, expected = turn["results"], (q["handbook"], q["figure_number"])
    return {
        "id": q["id"], "type": q["type"], "expected": " ".join(expected).strip(),
        "mode": turn["answer"]["mode"], "fallback_reason": turn["answer"]["fallback_reason"] or "",
        "sentences": len(turn["answer"]["sentences"]), "follow_ups": len(turn["follow_ups"]),
        "figures": len(results), "confidence": turn.get("confidence", ""),
        "rank_by_score": rank_of(by_score(results), *expected) or "",
        "rank_shown": rank_of(results, *expected) or "",
        "first_shown": f"{results[0]['handbook_id']} {results[0]['figure_id']}" if results else "",
        "latency_ms": ms,
    }


def followup_row(p, first, second, alone):
    expected = (p["handbook"], p["figure_number"])
    return {
        "id": p["id"], "expected": f"{expected[0]} {expected[1]}", "first_mode": first["answer"]["mode"],
        "follow_up": p["follow_up"], "rewritten": second["question"], "rewrite_fallback": second["rewrite_fallback"] or "",
        "mode_with_history": second["answer"]["mode"],
        "rank_with_history": rank_of(second["results"], *expected) or "",
        "rank_without_history": rank_of(alone["results"], *expected) or "",
        "check": "",
    }


def hits(ranks, n):
    return sum(1 for r in ranks if r != "" and int(r) <= n)


def summary_lines(label, single, follow, meta):
    answerable = [r for r in single if r["type"] != "no-answer"]
    no_answer = [r for r in single if r["type"] == "no-answer"]
    modes = {}
    for r in single:
        modes[r["mode"]] = modes.get(r["mode"], 0) + 1
    lines = [f"# Chat evaluation `{label}`", "",
             f"- Date (UTC): {meta['date']}; git commit: {meta['commit']}",
             f"- Embedding model: {meta['model']}; thresholds {meta['thresholds']}; top {K}; all handbooks", "",
             "## A. The 50 questions as the first message of a chat", "",
             f"- Answer modes: " + ", ".join(f"{m} {c}" for m, c in sorted(modes.items())),
             f"- No-answer questions answered \"no answer\": {sum(r['mode'] == 'no_answer' for r in no_answer)}/{len(no_answer)}",
             f"- Answerable questions answered \"no answer\": {sum(r['mode'] == 'no_answer' for r in answerable)}/{len(answerable)}",
             "", "| First figure = expected (answerable) | Hit@1 | Hit@5 |", "| --- | --- | --- |",
             f"| retrieval order (score) | {hits([r['rank_by_score'] for r in answerable], 1)}/{len(answerable)} "
             f"| {hits([r['rank_by_score'] for r in answerable], 5)}/{len(answerable)} |",
             f"| order shown by the chat (cited first) | {hits([r['rank_shown'] for r in answerable], 1)}/{len(answerable)} "
             f"| {hits([r['rank_shown'] for r in answerable], 5)}/{len(answerable)} |",
             "", "## B. Follow-up questions (10 pairs)", "",
             "| Follow-up searched | Hit@1 | Hit@5 |", "| --- | --- | --- |",
             f"| with history (chat, rewritten) | {hits([r['rank_with_history'] for r in follow], 1)}/{len(follow)} "
             f"| {hits([r['rank_with_history'] for r in follow], 5)}/{len(follow)} |",
             f"| without history (search box) | {hits([r['rank_without_history'] for r in follow], 1)}/{len(follow)} "
             f"| {hits([r['rank_without_history'] for r in follow], 5)}/{len(follow)} |",
             f"- Rewrites that fell back (LLM failure): {sum(1 for r in follow if r['rewrite_fallback'])}/{len(follow)}",
             "", "| Pair | Follow-up | Rewritten | rank with / without history |", "| --- | --- | --- | --- |"]
    lines += [f"| {r['id']} | {r['follow_up']} | {r['rewritten']} | {r['rank_with_history'] or '-'} / "
              f"{r['rank_without_history'] or '-'} |" for r in follow]
    return lines


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def error_turn(exc, question=""):
    """A failed turn, recorded instead of stopping the run."""
    return {"question": question, "results": [], "follow_ups": [], "rewrite_fallback": type(exc).__name__,
            "answer": {"mode": "error", "fallback_reason": f"{type(exc).__name__}: {exc}"[:200], "sentences": []}}


def safe(call, *args):
    try:
        return call(*args)
    except Exception as exc:          # quota, network, database: keep the other questions
        return error_turn(exc)


def read_rows(path):
    return read_csv(path) if path.exists() else []


def run(label, chat=chat_turn, retrieve=None, pause=PAUSE_SECONDS, sleep=time.sleep, parts="AB"):
    retrieve = retrieve or retrieval.retrieve
    out = RUNS / label
    out.mkdir(parents=True, exist_ok=True)
    single = read_rows(out / "chat_single.csv") if "A" not in parts else []
    for q in (read_csv(QUESTIONS) if "A" in parts else []):
        start = time.perf_counter()
        turn = safe(chat, q["question"], [], K)
        single.append(single_row(q, turn, round((time.perf_counter() - start) * 1000)))
        print(f"  {q['id']}: {turn['answer']['mode']} {turn['answer']['fallback_reason'] or ''}", flush=True)
        sleep(pause)
    if "A" in parts:
        write_csv(out / "chat_single.csv", single)
    follow = read_rows(out / "chat_followups.csv") if "B" not in parts else []
    for p in (read_csv(FOLLOWUPS) if "B" in parts else []):
        first = safe(chat, p["first_question"], [], K)
        sleep(pause)
        second = safe(chat, p["follow_up"], history_of(p["first_question"], first), K)
        alone = safe(retrieve, p["follow_up"], K)
        follow.append(followup_row(p, first, second, alone))
        print(f"  {p['id']}: {second['question']}", flush=True)
        sleep(pause)
    if "B" in parts:
        write_csv(out / "chat_followups.csv", follow)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    meta = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "commit": commit or "?",
            "model": retrieval.text_model(), "thresholds": retrieval.thresholds()}
    text = "\n".join(summary_lines(label, single, follow, meta)) + "\n"
    (out / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    return single, follow


def main():
    if len(sys.argv) not in (3, 4) or sys.argv[1] != "run" or (len(sys.argv) == 4 and sys.argv[3] not in ("A", "B")):
        sys.exit("Usage: python evaluation/chat_eval.py run <label> [A|B]")
    run(sys.argv[2], parts=sys.argv[3] if len(sys.argv) == 4 else "AB")


if __name__ == "__main__":
    main()
