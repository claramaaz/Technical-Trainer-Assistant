"""Tests of the database search in backend/retrieval.py (P7-22).

Run from the repository root:   python -m pytest -q tests/test_retrieval_db.py
They skip with a message if PostgreSQL is not running. The licence tests use a small made-up handbook
in a temporary database (like tests/test_load_db.py); the equivalence test uses the real database.
"""
import re

import numpy as np
import pytest

import load_db
from backend import retrieval
from backend.retrieval import NO_ANSWER, load_index_from, retrieve
from test_load_db import HID, MODEL, make_handbook, vectors

FIGURE_VECTORS = vectors(3, 1)   # the vectors make_handbook() stores for figures 1-1, 1-2, 2-1


def load_handbook(db, tmp_path, licence):
    make_handbook(tmp_path, licence=licence)
    load_db.load(db, load_db.read_sources(HID, MODEL, tmp_path))
    db.commit()


def ask_for_figure_1_1(index):
    # The question vector is exactly the stored vector of figure 1-1: score 1.0, far above THRESHOLD.
    return retrieve("anything", k=3, index=index, query_vector=FIGURE_VECTORS[0])


def test_known_licence_is_found(db, pg_test_dsn, tmp_path):
    # control for the next tests: the same question does return figure 1-1 when the licence is known
    load_handbook(db, tmp_path, "Public domain")
    out = ask_for_figure_1_1(load_index_from(pg_test_dsn))
    assert out["reason"] is None
    top = out["results"][0]
    assert top["figure_id"] == "1-1" and top["handbook"] == "Test Handbook"
    assert top["score"] == pytest.approx(1.0, abs=1e-6)
    assert top["passage"] == "Airspace is shown in [Figure 1-1]."          # first citing paragraph
    assert out["results"][2]["passage"] == ""                               # figure 2-1 has none


@pytest.mark.parametrize("licence", ["unknown", "Unknown", ""])
def test_document_with_unknown_licence_returns_no_results(db, pg_test_dsn, tmp_path, licence):
    load_handbook(db, tmp_path, licence)
    assert db.execute("SELECT count(*) FROM figures").fetchone()[0] == 3   # the rows ARE in the database
    out = ask_for_figure_1_1(load_index_from(pg_test_dsn))
    assert out == {"results": [], "reason": NO_ANSWER}


def test_licence_removed_after_the_index_was_built_still_returns_nothing(db, pg_test_dsn, tmp_path):
    # load_index() is cached for a long time; the ranking must still look at the licence each time.
    load_handbook(db, tmp_path, "Public domain")
    index = load_index_from(pg_test_dsn)
    assert ask_for_figure_1_1(index)["reason"] is None
    db.execute("UPDATE documents SET licence = NULL WHERE id = %s", (HID,))
    db.commit()
    assert ask_for_figure_1_1(index) == {"results": [], "reason": NO_ANSWER}


def test_document_that_is_not_fully_loaded_returns_no_results(db, pg_test_dsn, tmp_path):
    load_handbook(db, tmp_path, "Public domain")
    db.execute("UPDATE documents SET status = 'failed' WHERE id = %s", (HID,))
    db.commit()
    assert ask_for_figure_1_1(load_index_from(pg_test_dsn)) == {"results": [], "reason": NO_ANSWER}


def test_search_code_reads_only_the_searchable_views():
    sql = retrieval.DESCRIBE_SQL + retrieval.RANK_SQL
    tables = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql, flags=re.I))
    assert tables == {"searchable_figures", "searchable_figure_refs"}


def test_score_is_one_minus_cosine_distance(db, pg_test_dsn, tmp_path):
    load_handbook(db, tmp_path, "Public domain")
    q = vectors(1, 99)[0]
    ranked = retrieval.rank(load_index_from(pg_test_dsn), q, 3)
    cosines = sorted((float(v @ q) for v in FIGURE_VECTORS), reverse=True)
    assert [s for _, s in ranked] == pytest.approx(cosines, abs=1e-6)


def test_database_ranking_equals_the_file_ranking_for_every_question(real_index):
    # Needs the extracted files too (the reference is the old file-based search).
    import sys
    sys.path.insert(0, str(retrieval.ROOT / "evaluation"))
    import compare_db_files
    if not (retrieval.ROOT / "data" / "extracted" / compare_db_files.HANDBOOK / "figures.jsonl").exists():
        pytest.skip("data/extracted/... missing: the file-based reference cannot be computed")
    rows = compare_db_files.compare()
    assert len(rows) >= 25
    assert [r["q"]["id"] for r in rows if not r["ok"]] == []
