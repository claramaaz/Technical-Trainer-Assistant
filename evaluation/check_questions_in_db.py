"""Check that every answerable question points at a figure that exists in the database (read-only).

Usage (repository root, database running and loaded):
    python evaluation/check_questions_in_db.py

For each question in evaluation/questions.csv that is not a no-answer question, look up
(handbook, figure_number) in the figures table and compare the printed page. Prints how many
questions were checked and the ids that are missing or have a different printed page.
Nothing is written to the database or to the CSV.
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUESTIONS = ROOT / "evaluation" / "questions.csv"


def load_answerable(path=QUESTIONS):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r["type"].strip().lower() != "no-answer"]


def fetch_pages(conn):
    """{(handbook, figure_number): printed_page} for every figure in the database."""
    rows = conn.execute("SELECT document_id, figure_number, printed_page FROM figures").fetchall()
    return {(d, n): p for d, n, p in rows}


def check(questions, pages):
    """Return (missing_ids, different_page_ids)."""
    missing, different = [], []
    for q in questions:
        key = (q["handbook"].strip(), q["figure_number"].strip())
        if key not in pages:
            missing.append(q["id"].strip())
        elif pages[key] != q["printed_page"].strip():
            different.append(q["id"].strip())
    return missing, different


def main():
    import psycopg
    from ingestion.migrate import connection_string

    questions = load_answerable()
    with psycopg.connect(connection_string()) as conn:
        pages = fetch_pages(conn)
    missing, different = check(questions, pages)
    print(f"Answerable questions checked: {len(questions)}")
    print(f"Figure not in database: {', '.join(missing) or 'none'}")
    print(f"Printed page differs: {', '.join(different) or 'none'}")


if __name__ == "__main__":
    main()
