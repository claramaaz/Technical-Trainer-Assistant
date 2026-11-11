"""Test of the chunk -> figure ranking in the real database (P7-30, "passages" mode), written from
SRS UC-02 step 3 ("the system searches the stored text and figures together") and BR-001.

A made-up handbook (tests/test_load_db.py): the first chunk ("Chunk 1") cites figure 1-1 and is the only chunk that
cites a figure. Skipped if PostgreSQL is not running.   Run:   python -m pytest -q tests/test_chunk_ranking_db.py
"""
import load_db
from backend import retrieval
from backend.retrieval import load_index_from
from test_load_db import HID, MODEL, make_handbook, vectors

CHUNK_VECTORS = vectors(4, 2)   # the vectors make_handbook() stores for its 4 chunks


def load(db, tmp_path, licence="Public domain"):
    make_handbook(tmp_path, licence=licence)
    load_db.load(db, load_db.read_sources(HID, MODEL, tmp_path))
    db.commit()


def test_a_question_close_to_the_chunk_finds_the_figure_the_chunk_cites(db, pg_test_dsn, tmp_path):
    load(db, tmp_path)
    index = load_index_from(pg_test_dsn)
    ranked = retrieval.rank_chunks(index, CHUNK_VECTORS[0], k=10)     # exactly chunk 1: score 1.0
    figure_1_1 = db.execute("SELECT id FROM figures WHERE figure_number = '1-1'").fetchone()[0]
    assert [(f, round(score, 5)) for f, score in ranked] == [(figure_1_1, 1.0)]


def test_chunks_of_a_handbook_with_unknown_licence_are_never_used(db, pg_test_dsn, tmp_path):
    load(db, tmp_path, licence="unknown")
    index = load_index_from(pg_test_dsn)
    assert retrieval.rank_chunks(index, CHUNK_VECTORS[0], k=10) == []
