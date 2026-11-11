"""Evaluation run on the LIVE search (P7-17; brief section 8, FR-005, UC-06 steps 2-4, SPEC 5.3).

Usage (from the repository root, database running):
    python evaluation/run_eval.py run   <label> [text|image|joint|passages|hybrid]   # ask every question, write runs/<label>/
    python evaluation/run_eval.py score <label>   # recompute the summary after judgements were added

The optional mode (P7-30) is the retrieval mode of backend/retrieval.py; without it, RETRIEVAL_MODE
(environment or .env, default text). It is written in meta.txt and in the summary.

'run' asks every question of evaluation/questions.csv in two scopes:
    own = only the handbook named in the question (comparable with the 15B-only baseline, EVALUATION 3.3)
    all = every searchable handbook (what a learner gets)
and keeps, for each scope:
    - the top 5 figures from rank(): the same database query as GET /search, BEFORE the threshold;
    - whether retrieve() answers or says "no answer found": the threshold of the live system.
It writes runs/<label>/ranked.csv (one row per returned figure) and adds every new
(question, handbook, figure) pair of an answerable question to evaluation/judgements.csv.

Human judgements (SPEC 5.3), evaluation/judgements.csv, column score:
    2 = the expected figure. Pre-filled, because SPEC 5.3 defines 2 as the expected figure.
        A person may also give 2 to another figure that is just as correct
        (for example the same diagram in the other handbook; EVALUATION 3.3).
    1 = related but not the expected figure;  0 = not relevant;  empty = not judged yet.
A score that is already written is never changed by this script.
Figures are identified by handbook id + printed figure number, not by database id,
so the judgements survive a reload of the database.

Two sets of metrics are reported:
    auto  = a hit is the expected figure (same handbook AND same figure number);
    human = a hit is a figure scored 2; computed only on questions whose 5 figures are all judged.
"""
import csv
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))
from backend import retrieval  # noqa: E402  (retrieval.rank is looked up at call time: tests replace it)
from baseline_retrieval import TOP_K, summarize  # noqa: E402

QUESTIONS = ROOT / "evaluation" / "questions.csv"
JUDGEMENTS = ROOT / "evaluation" / "judgements.csv"
RUNS = ROOT / "evaluation" / "runs"
SCOPES = ("own", "all")
RANKED_FIELDS = ["question_id", "type", "scope", "answered", "rank", "db_id", "handbook_id",
                 "figure_number", "printed_page", "score", "expected"]
JUDGEMENT_FIELDS = ["question_id", "handbook_id", "figure_number", "score", "judge", "note"]
EXPECTED_JUDGE = "expected figure (SPEC 5.3)"


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, fields, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:   # csv writes CRLF line endings
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def answerable(question):
    return question["type"] != "no-answer"


def run_questions(questions, index, embed=None, k=TOP_K, mode="text"):
    """One row per returned figure, for every question and scope (see the module docstring).

    mode: "text", "image" or "joint" (P7-30): the same ranking as the live search in that mode."""
    embed = embed or retrieval.embed_query
    rows = []
    for q in questions:
        vector = embed(q["question"])
        for scope in SCOPES:
            handbooks = [q["handbook"]] if scope == "own" else None
            ranked, _best_text = retrieval.rank_query(index, q["question"], vector, k, handbooks, mode)
            if not ranked:
                raise RuntimeError(f"{q['id']}: no figure returned in scope {scope}: is the database empty?")
            found = retrieval.retrieve(q["question"], k, index, vector, handbooks, mode)
            for position, (figure_db_id, score) in enumerate(ranked, start=1):
                d = index.documents[figure_db_id]
                rows.append({
                    "question_id": q["id"], "type": q["type"], "scope": scope,
                    "answered": int(found["reason"] is None), "rank": position, "db_id": figure_db_id,
                    "handbook_id": d["handbook_id"], "figure_number": d["figure_number"],
                    "printed_page": d["printed_page"], "score": f"{score:.4f}",
                    "expected": int(answerable(q) and d["handbook_id"] == q["handbook"]
                                    and d["figure_number"] == q["figure_number"]),
                })
    return rows


def key(row):
    return row["question_id"], row["handbook_id"], row["figure_number"]


def merge_judgements(existing, ranked_rows):
    """existing rows unchanged, plus one new row per new pair of an answerable question."""
    merged = list(existing)
    seen = {key(r) for r in existing}
    for r in ranked_rows:
        if r["type"] == "no-answer" or key(r) in seen:
            continue
        seen.add(key(r))
        is_expected = str(r["expected"]) == "1"
        merged.append({"question_id": r["question_id"], "handbook_id": r["handbook_id"],
                       "figure_number": r["figure_number"], "score": "2" if is_expected else "",
                       "judge": EXPECTED_JUDGE if is_expected else "", "note": ""})
    return merged


def scores_from(judgements):
    """{(question, handbook, figure): 0|1|2} for the rows that are judged. A bad value stops the run."""
    scores = {}
    for r in judgements:
        value = (r.get("score") or "").strip()
        if value == "":
            continue
        if value not in ("0", "1", "2"):
            raise ValueError(f"judgements.csv: score must be 0, 1, 2 or empty, got {value!r} for {key(r)}")
        scores[key(r)] = int(value)
    return scores


def group(rows):
    """{(question_id, scope): [rows in rank order]}"""
    out = {}
    for r in rows:
        out.setdefault((r["question_id"], r["scope"]), []).append(r)
    for v in out.values():
        v.sort(key=lambda r: int(r["rank"]))
    return out


def auto_rank(rows):
    return next((int(r["rank"]) for r in rows if str(r["expected"]) == "1"), None)


def human_rank(rows, scores):
    """(rank of the first figure scored 2 or None, True if every figure is judged)."""
    complete = all(key(r) in scores for r in rows)
    first = next((int(r["rank"]) for r in rows if scores.get(key(r)) == 2), None)
    return first, complete


def evaluate_run(ranked_rows, questions, scores):
    """Metrics per scope, as plain numbers (used by the summary and by the tests)."""
    groups = group(ranked_rows)
    by_type = {q["id"]: q["type"] for q in questions}
    result = {}
    for scope in SCOPES:
        ids = [qid for (qid, s) in groups if s == scope]
        ans = [i for i in ids if by_type.get(i) != "no-answer"]
        noans = [i for i in ids if by_type.get(i) == "no-answer"]
        auto = [auto_rank(groups[(i, scope)]) for i in ans]
        human = [human_rank(groups[(i, scope)], scores) for i in ans]
        human_done = [r for r, complete in human if complete]
        answered = {i: str(groups[(i, scope)][0]["answered"]) == "1" for i in ids}
        result[scope] = {
            "answerable": len(ans), "no_answer": len(noans),
            "auto": summarize(auto) if auto else None,
            "auto_ranks": dict(zip(ans, auto)),
            "human": summarize(human_done) if human_done else None,
            "human_judged": len(human_done),
            "human_ranks": {i: r for i, (r, complete) in zip(ans, human) if complete},
            "no_answer_correct": sum(1 for i in noans if not answered[i]),
            "false_refusals": [i for i in ans if not answered[i]],
            "top1": {i: (groups[(i, scope)][0]["handbook_id"], groups[(i, scope)][0]["figure_number"],
                         float(groups[(i, scope)][0]["score"])) for i in ids},
        }
    return result


def fmt(metrics):
    if metrics is None:
        return "n/a | n/a | n/a"
    return f"{metrics['Hit@1']:.3f} | {metrics[f'Hit@{TOP_K}']:.3f} | {metrics[f'MRR@{TOP_K}']:.3f}"


def mode_details(mode):
    """What the retrieval mode used, for the summary (P7-30): only the parts that mode really uses."""
    parts = []
    if mode in ("image", "joint"):
        parts.append(f"image model {retrieval.IMAGE_MODEL_NAME}")
    if mode in ("passages", "hybrid"):
        parts.append(f"{retrieval.CHUNK_CANDIDATES} nearest passages")
    if mode in ("joint", "hybrid"):
        parts.append(f"RRF k={retrieval.RRF_K}, {retrieval.CANDIDATES} candidates per list")
    return f" ({'; '.join(parts)})" if parts else ""


def summary_text(label, result, questions, meta):
    lines = [f"# Evaluation run `{label}`", "",
             f"- Date (UTC): {meta.get('date', '?')}; git commit: {meta.get('commit', '?')}",
             f"- Model: {retrieval.MODEL_NAME}; threshold: {retrieval.THRESHOLD}; top {TOP_K}",
             f"- Retrieval mode: {meta.get('mode', 'text')}" + mode_details(meta.get("mode", "text")),
             f"- Questions: {len(questions)} ({sum(answerable(q) for q in questions)} answerable, "
             f"{sum(not answerable(q) for q in questions)} no-answer)",
             "- own = only the question's handbook; all = every searchable handbook", "",
             "| Scope | Metric rule | Questions | Hit@1 | Hit@5 | MRR@5 |", "| --- | --- | --- | --- | --- | --- |"]
    for scope in SCOPES:
        r = result[scope]
        lines.append(f"| {scope} | auto (expected figure) | {r['answerable']} | {fmt(r['auto'])} |")
        lines.append(f"| {scope} | human (scored 2) | {r['human_judged']} of {r['answerable']} judged | "
                     f"{fmt(r['human'])} |")
    lines += ["", "| Scope | No-answer accuracy | Answerable questions refused by the threshold |",
              "| --- | --- | --- |"]
    for scope in SCOPES:
        r = result[scope]
        acc = f"{r['no_answer_correct']}/{r['no_answer']}" if r["no_answer"] else "n/a"
        refused = ", ".join(r["false_refusals"]) or "none"
        lines.append(f"| {scope} | {acc} | {len(r['false_refusals'])}/{r['answerable']}: {refused} |")
    lines += ["", "Per question: rank of the expected figure (auto), '-' = not in the top 5; top-1 returned.", "",
              "| Question | Type | Expected | own rank | all rank | all top-1 (score) |",
              "| --- | --- | --- | --- | --- | --- |"]
    for q in questions:
        own, all_ = result["own"], result["all"]
        top = all_["top1"].get(q["id"])
        expected = f"{q['handbook']} {q['figure_number']}" if answerable(q) else "(no answer)"
        def show(r):
            return str(r["auto_ranks"].get(q["id"]) or "-") if answerable(q) else "-"
        top_txt = f"{top[0]} {top[1]} ({top[2]:.3f})" if top else "-"
        lines.append(f"| {q['id']} | {q['type']} | {expected} | {show(own)} | {show(all_)} | {top_txt} |")
    return "\n".join(lines) + "\n"


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def check_label(label):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", label):
        sys.exit("label: letters, digits, '.', '_' and '-' only (e.g. baseline-v2)")
    return RUNS / label


def score_run(label, meta=None):
    folder = check_label(label)
    ranked = read_csv(folder / "ranked.csv")
    if not ranked:
        sys.exit(f"{folder / 'ranked.csv'} not found: run first")
    meta = meta or dict(r.split(": ", 1) for r in (folder / "meta.txt").read_text(encoding="utf-8").splitlines()
                        if ": " in r)
    questions = read_csv(QUESTIONS)
    text = summary_text(label, evaluate_run(ranked, questions, scores_from(read_csv(JUDGEMENTS))), questions, meta)
    with open(folder / "summary.md", "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(text)
    print(text)
    print(f"Saved to {folder / 'summary.md'}")


def run(label, mode=None):
    folder = check_label(label)
    if (folder / "ranked.csv").exists():
        sys.exit(f"{folder} already exists: choose a new label (runs are kept as evidence)")
    mode = mode or retrieval.retrieval_mode()
    if mode not in retrieval.MODES:
        sys.exit(f"mode must be one of {retrieval.MODES}")
    questions = read_csv(QUESTIONS)
    rows = run_questions(questions, retrieval.load_index(), mode=mode)
    meta = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "commit": git_commit(), "mode": mode}
    write_csv(folder / "ranked.csv", RANKED_FIELDS, rows)
    with open(folder / "meta.txt", "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("".join(f"{k}: {v}\n" for k, v in meta.items()))
    before = read_csv(JUDGEMENTS)
    merged = merge_judgements(before, rows)
    write_csv(JUDGEMENTS, JUDGEMENT_FIELDS, merged)
    todo = sum(1 for r in merged if not r["score"])
    print(f"{len(merged) - len(before)} new pairs added to {JUDGEMENTS.name}; {todo} still to judge.")
    score_run(label, meta)


def main():
    args = sys.argv[1:]
    if args[:1] == ["run"] and len(args) in (2, 3):
        run(args[1], args[2] if len(args) == 3 else None)
    elif args[:1] == ["score"] and len(args) == 2:
        score_run(args[1])
    else:
        sys.exit("Usage: python evaluation/run_eval.py run <label> [text|image|joint|passages|hybrid]  |  score <label>")


if __name__ == "__main__":
    main()
