"""Help the team WRITE the evaluation questions (the brief: "written by your
team"). This script writes no questions. It only shows what each figure is
about, and checks the questions you wrote.

Step 1, make the helper page (from the repository root):
    python evaluation/question_helper.py sheet FAA-H-8083-15B

  Writes data/extracted/<id>/question_helper.html. Open it in a browser: for
  every figure it shows the image, its number, printed page, caption and the
  handbook paragraph that explains it. Read the paragraph, then write the
  question a learner would ask whose best answer is that figure.

Step 2, write your questions in evaluation/questions.csv (one row each):
    id            Q001, Q002 ... (Clara Q001-Q025, Mia Q026-Q050)
    question      in your own words, as a learner would type it
    type          topic | symptom | no-answer
    handbook      FAA-H-8083-15B (empty for no-answer)
    figure_number e.g. 4-11 (empty for no-answer)
    printed_page  as printed in the handbook, e.g. 4-8 (empty for no-answer)
    author        Clara or Mia
  Open it in a text editor, or in Excel and save as "CSV UTF-8".

Step 3, check them:
    python evaluation/question_helper.py check FAA-H-8083-15B

  Reports figure numbers that do not exist, printed pages that do not match
  the figure, repeated ids, missing columns, and the mix of question types.
"""
import csv
import html
import json
import sys
from collections import Counter
from pathlib import Path

QUESTIONS = Path("evaluation") / "questions.csv"
COLUMNS = ["id", "question", "type", "handbook", "figure_number", "printed_page", "author"]
TYPES = {"topic", "symptom", "no-answer"}


def load_figures(handbook_id):
    path = Path("data") / "extracted" / handbook_id / "figures.jsonl"
    if not path.exists():
        sys.exit(f"{path} not found: run ingestion/extract_figures.py first.")
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def sheet(handbook_id):
    figures = [f for f in load_figures(handbook_id) if f["status"] == "bound"]
    cards = []
    for f in figures:
        refs = f.get("referencing_paragraphs") or []
        explain = refs[0]["text"] if refs else "(no paragraph in the handbook mentions this figure)"
        cards.append(
            f"<div class=c id='fig-{html.escape(f['figure_number'])}'>"
            f"<img loading=lazy src='{html.escape(f['image_path'])}'>"
            f"<div><p class=n>Figure {html.escape(f['figure_number'])} &middot; printed page "
            f"{html.escape(f['printed_page'])} &middot; PDF page {f['pdf_page']}</p>"
            f"<p class=cap>{html.escape(f['caption'])}</p>"
            f"<p class=ex><b>What the handbook says about it:</b> {html.escape(explain)}</p></div></div>")
    page = (
        "<meta charset=utf-8><title>Question helper</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:1000px;margin:auto;padding:0 16px;color:#222}"
        ".c{display:grid;grid-template-columns:320px 1fr;gap:16px;border-top:1px solid #ccc;padding:16px 0}"
        "img{max-width:320px;max-height:300px}.n{font-weight:600;margin:0}.cap{font-style:italic}"
        ".ex{font-size:14px;line-height:1.45}"
        "@media(max-width:700px){.c{grid-template-columns:1fr}}</style>"
        f"<h1>Question helper: {html.escape(handbook_id)} ({len(figures)} figures)</h1>"
        "<p>For each figure: read the caption and the paragraph, then ask yourself <i>what would a "
        "learner type, if this figure were the best answer?</i> Write it in your own words in "
        "evaluation/questions.csv. Topic questions ask how something works; symptom questions "
        "describe something the pilot observes.</p>" + "".join(cards))
    out = Path("data") / "extracted" / handbook_id / "question_helper.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({len(figures)} figures). Open it in your browser.")


def check(handbook_id):
    figures = {f["figure_number"]: f for f in load_figures(handbook_id)}
    if not QUESTIONS.exists():
        sys.exit(f"{QUESTIONS} not found.")
    rows = list(csv.DictReader(open(QUESTIONS, encoding="utf-8-sig")))
    problems = []
    if rows and set(COLUMNS) - set(rows[0].keys()):
        sys.exit(f"Missing columns: {sorted(set(COLUMNS) - set(rows[0].keys()))}")
    ids = Counter(r["id"].strip() for r in rows)
    problems += [f"id {i} is used {n} times" for i, n in ids.items() if n > 1]
    for r in rows:
        rid, kind = r["id"].strip(), r["type"].strip().lower()
        if not r["question"].strip():
            problems.append(f"{rid}: empty question")
        if kind not in TYPES:
            problems.append(f"{rid}: type '{r['type']}' is not one of {sorted(TYPES)}")
        if kind == "no-answer":
            if r["figure_number"].strip():
                problems.append(f"{rid}: a no-answer question should have no figure")
            continue
        number = r["figure_number"].strip()
        if r["handbook"].strip() != handbook_id:
            problems.append(f"{rid}: handbook '{r['handbook']}' (expected {handbook_id})")
        if number not in figures:
            problems.append(f"{rid}: figure {number!r} does not exist in {handbook_id}"
                            " (Excel may have turned it into a date)")
        elif r["printed_page"].strip() != figures[number]["printed_page"]:
            problems.append(f"{rid}: figure {number} is on printed page "
                            f"{figures[number]['printed_page']}, not {r['printed_page']!r}")
    kinds = Counter(r["type"].strip().lower() for r in rows)
    authors = Counter(r["author"].strip() for r in rows)
    print(f"{len(rows)} questions; types: {dict(kinds)}; authors: {dict(authors)}")
    print("\n".join(problems) if problems else "No problems found.")
    if len(rows) < 50:
        print(f"The brief asks for at least 50 questions: {50 - len(rows)} to go.")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("sheet", "check"):
        sys.exit("Usage: python evaluation/question_helper.py sheet|check <handbook-id>")
    sheet(sys.argv[2]) if sys.argv[1] == "sheet" else check(sys.argv[2])


if __name__ == "__main__":
    main()
