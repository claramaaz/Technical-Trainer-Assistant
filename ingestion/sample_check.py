"""Draw a random sample of figure-caption pairs for the manual check (Week 1 gate).

Step 1, draw the sample (from the repository root):
    python ingestion/sample_check.py draw FAA-H-8083-15B --n 20 --seed 7

  Writes, in data/extracted/<id>/:
    check_sample.csv   one row per sampled figure, with EMPTY judgement columns
    check_sample.html  open it in a browser: each figure image next to its
                       stored caption and page, so you can compare with the PDF

Step 2, judge each row: open the original PDF at pdf_page and fill in
    caption_correct : y if the stored caption belongs to this image, else n
    page_correct    : y if printed_page is the page number printed on that page
    image_complete  : y if the PNG shows the whole figure (not cut, not merged)
    notes           : anything odd
  Save the CSV (in Excel: "CSV UTF-8"). Excel turns numbers like 1-20 into
  dates (20-Jan); "score" repairs those two columns from figures.jsonl.

Step 3, score it:
    python ingestion/sample_check.py score FAA-H-8083-15B

  Prints the accuracies to paste into EVALUATION.md. Copy check_sample.csv to
  evaluation/ and commit it: the judged sample is evidence.

The seed makes the sample reproducible: anyone running "draw" with the same
seed on the same figures.jsonl gets the same 20 figures.
"""
import argparse
import csv
import html
import json
import random
import sys
from pathlib import Path

COLUMNS = ["figure_number", "pdf_page", "printed_page", "image_path", "caption",
           "caption_correct", "page_correct", "image_complete", "notes"]
JUDGED = ["caption_correct", "page_correct", "image_complete"]


def draw(folder, n, seed):
    figures = [json.loads(line) for line in open(folder / "figures.jsonl", encoding="utf-8")]
    bound = [f for f in figures if f["status"] == "bound"]
    if len(bound) < n:
        sys.exit(f"Only {len(bound)} bound figures; cannot sample {n}.")
    sample = random.Random(seed).sample(bound, n)
    sample.sort(key=lambda f: f["pdf_page"])
    csv_path = folder / "check_sample.csv"
    if csv_path.exists():
        sys.exit(f"{csv_path} already exists. Delete it first if you really want a new sample.")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for f in sample:
            w.writerow({k: f.get(k, "") for k in COLUMNS})
    cards = "".join(
        f"<div class=c><img src='{html.escape(f['image_path'])}'>"
        f"<p><b>Figure {html.escape(f['figure_number'])}</b> · PDF page {f['pdf_page']} · "
        f"printed page {html.escape(f['printed_page'] or '?')}</p>"
        f"<p>{html.escape(f['caption'])}</p></div>" for f in sample)
    (folder / "check_sample.html").write_text(
        "<meta charset=utf-8><title>Caption check</title><style>body{font-family:sans-serif;"
        "max-width:900px;margin:auto}.c{border:1px solid #ccc;margin:12px 0;padding:8px}"
        f"img{{max-width:100%;max-height:420px}}</style><h1>Sample (seed {seed}, n={n})</h1>{cards}",
        encoding="utf-8")
    print(f"Wrote {csv_path} and check_sample.html ({n} figures, seed {seed}, "
          f"drawn from {len(bound)} bound figures)")


def restore_excel_damage(folder, rows):
    """Excel silently turns "1-20" into the date "20-Jan" when it opens a CSV.
    image_path is never converted, so use it to restore the figure number and
    printed page from figures.jsonl. Returns how many values were repaired."""
    figures = {}
    for line in open(folder / "figures.jsonl", encoding="utf-8"):
        f = json.loads(line)
        figures[f["image_path"]] = f
    repaired = 0
    for r in rows:
        f = figures[r["image_path"]]
        for key in ("figure_number", "printed_page"):
            if r[key] != f[key]:
                r[key] = f[key]
                repaired += 1
    return repaired


def score(folder):
    rows = list(csv.DictReader(open(folder / "check_sample.csv", encoding="utf-8-sig")))
    repaired = restore_excel_damage(folder, rows)
    if repaired:
        with open(folder / "check_sample.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        print(f"Repaired {repaired} values that Excel had turned into dates.")
    for col in JUDGED:
        answers = [r[col].strip().lower() for r in rows]
        blank = sum(1 for a in answers if a not in ("y", "n"))
        if blank:
            sys.exit(f"{blank} rows have no y/n in '{col}'. Finish judging first.")
    print(f"Sample size: {len(rows)}")
    for col in JUDGED:
        ok = sum(1 for r in rows if r[col].strip().lower() == "y")
        print(f"{col:16}: {ok}/{len(rows)} = {ok / len(rows):.0%}")
    wrong = [r["figure_number"] for r in rows if r["caption_correct"].strip().lower() == "n"]
    print("Wrong captions  :", ", ".join(wrong) or "none")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["draw", "score"])
    p.add_argument("handbook_id")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()
    folder = Path("data") / "extracted" / a.handbook_id
    draw(folder, a.n, a.seed) if a.action == "draw" else score(folder)


if __name__ == "__main__":
    main()
