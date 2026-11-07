"""Test for evaluation/check_questions_in_db.py with a fake data source (no database)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))
import check_questions_in_db as cq  # noqa: E402


def q(qid, number, page, handbook="HB-A"):
    return {"id": qid, "handbook": handbook, "figure_number": number, "printed_page": page}


def test_reports_missing_and_different_page():
    fake_db = {("HB-A", "3-1"): "3-3", ("HB-A", "4-2"): "4-5", ("HB-B", "3-1"): "3-7"}
    questions = [
        q("Q1", "3-1", "3-3"),                 # fine
        q("Q2", "9-9", "9-1"),                 # figure not in the database
        q("Q3", "4-2", "4-6"),                 # printed page differs
        q("Q4", "3-1", "3-3", handbook="HB-B"),  # same number, other handbook: page differs
    ]
    missing, different = cq.check(questions, fake_db)
    assert missing == ["Q2"]
    assert different == ["Q3", "Q4"]
