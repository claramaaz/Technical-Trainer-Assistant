"""Tests for ingestion/load_db.py on a temporary database (skipped if PostgreSQL is not running).

Run from the repository root:   python -m pytest -q tests/test_load_db.py

A small made-up handbook is written to a temporary folder (3 figures, 3 referencing
paragraphs, 4 chunks, 5 pages, random vectors): the real 71 MB handbook is not used.
Counts are worked out by hand from make_handbook().
"""
import csv
import json

import numpy as np
import pytest

import load_db

HID = "TEST-1"
MODEL = "test/model"
WANT = {"pages": 5, "figures": 3, "figure_refs": 3, "chunks": 4}


def vectors(n, seed):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 384)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def make_handbook(root, licence="Public domain", retrieved_at="2026-10-24T05:56:35+00:00"):
    (root / "corpus").mkdir(parents=True)
    with open(root / "corpus" / "handbooks.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "title", "url", "licence"])
        w.writerow([HID, "Test Handbook", "https://example.org/test.pdf", licence])
    (root / "data" / "raw").mkdir(parents=True)
    meta = {"id": HID, "sha256": "ab" * 32, "bytes": 1234}
    if retrieved_at:
        meta["retrieved_at"] = retrieved_at
    (root / "data" / "raw" / f"{HID}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (root / "data" / "inspect").mkdir(parents=True)
    with open(root / "data" / "inspect" / f"{HID}_pages.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["pdf_page", "printed_page", "text_chars"])
        for pdf, printed in [(1, ""), (2, ""), (3, "1-1"), (4, "1-2"), (5, "2-1")]:
            w.writerow([pdf, printed, 100])
    folder = root / "data" / "extracted" / HID
    folder.mkdir(parents=True)
    (folder / "report.json").write_text(json.dumps({"pdf_pages": 5}), encoding="utf-8")

    def ref(pdf, printed, text):
        return {"pdf_page": pdf, "printed_page": printed, "text": text}

    figures = [
        {"handbook_id": HID, "figure_number": "1-1", "caption": "Figure 1-1. Airspace.", "pdf_page": 3,
         "printed_page": "1-1", "caption_bbox": [1.0, 2.0, 3.0, 4.0], "status": "bound", "bbox": [5.0, 6.0, 7.0, 8.0],
         "rotation": 0, "image_path": "figures/1-1.png",
         "referencing_paragraphs": [ref(3, "1-1", "Airspace is shown in [Figure 1-1]."),
                                    ref(4, "1-2", "See Figure 1-1 again.")]},
        {"handbook_id": HID, "figure_number": "1-2", "caption": "Figure 1-2. Victor airways.", "pdf_page": 4,
         "printed_page": "1-2", "caption_bbox": [1.0, 2.0, 3.0, 4.0], "status": "bound", "bbox": [5.0, 6.0, 7.0, 8.0],
         "rotation": 90, "needs_review": "crop contains a body paragraph", "image_path": "figures/1-2.png",
         "referencing_paragraphs": [ref(4, "1-2", "Victor airways [Figure 1-2].")]},
        {"handbook_id": HID, "figure_number": "2-1", "caption": "Figure 2-1. Charts.", "pdf_page": 5,
         "printed_page": "2-1", "caption_bbox": [1.0, 2.0, 3.0, 4.0], "status": "bound", "bbox": [5.0, 6.0, 7.0, 8.0],
         "rotation": 0, "image_path": "figures/2-1.png", "referencing_paragraphs": []},
    ]
    chunks = [
        {"chunk_id": f"{HID}-c000{i}", "handbook_id": HID, "chapter": "1" if i < 3 else "2",
         "heading_path": ["Intro"], "text": f"Chunk {i} text.", "embed_text": f"Intro\n\nChunk {i} text.",
         "words": 3, "pdf_pages": [3], "printed_pages": ["1-1"], "figure_mentions": ["1-1"] if i == 1 else []}
        for i in range(1, 5)
    ]
    write_jsonl(folder / "figures.jsonl", figures)
    write_jsonl(folder / "chunks.jsonl", chunks)
    slug = MODEL.replace("/", "_")
    np.save(folder / f"figure_embeddings_full_{slug}.npy", vectors(3, 1))
    np.save(folder / f"chunk_embeddings_{slug}.npy", vectors(4, 2))
    return folder


@pytest.fixture
def root(tmp_path):
    make_handbook(tmp_path)
    return tmp_path


def sources(root):
    return load_db.read_sources(HID, MODEL, root)


def scalar(conn, sql, *args):
    value = conn.execute(sql, args).fetchone()[0]
    conn.commit()
    return value


def status(conn):
    row = conn.execute("SELECT status, searchable FROM documents WHERE id = %s", (HID,)).fetchone()
    conn.commit()
    return row


def visible(conn):
    figures = scalar(conn, "SELECT count(*) FROM searchable_figures")
    chunks = scalar(conn, "SELECT count(*) FROM searchable_chunks")
    return figures, chunks


# --- counts and content -------------------------------------------------------------------

def test_counts_match_the_files_and_the_document_is_loaded_and_searchable(db, root):
    counts = load_db.load(db, sources(root))
    assert counts == WANT
    assert load_db.database_counts(db, HID) == WANT
    assert status(db) == ("loaded", True)
    assert visible(db) == (3, 4)
    assert scalar(db, "SELECT loaded_at IS NOT NULL FROM documents WHERE id = %s", HID)


def test_stored_values(db, root):
    load_db.load(db, sources(root))
    doc = db.execute("SELECT title, source_url, licence, retrieved_at::text, sha256, bytes, pdf_pages, embedding_model "
                     "FROM documents").fetchone()
    assert doc[:3] == ("Test Handbook", "https://example.org/test.pdf", "Public domain")
    assert doc[3].startswith("2026-10-24 05:56:35")
    assert doc[4:] == ("ab" * 32, 1234, 5, MODEL)
    fig = db.execute("SELECT chapter, printed_page, image_path, needs_review, rotation, bbox "
                     "FROM figures WHERE figure_number = '1-2'").fetchone()
    assert fig == ("1", "1-2", f"{HID}/figures/1-2.png", True, 90, [5.0, 6.0, 7.0, 8.0])
    assert scalar(db, "SELECT needs_review FROM figures WHERE figure_number = '1-1'") is False
    assert scalar(db, "SELECT chapter FROM figures WHERE figure_number = '2-1'") == "2"
    # the references keep their order: position 0 is the first paragraph of the file
    refs = db.execute("SELECT r.position, r.text FROM figure_refs r JOIN figures f ON f.id = r.figure_id "
                      "WHERE f.figure_number = '1-1' ORDER BY r.position").fetchall()
    assert refs == [(0, "Airspace is shown in [Figure 1-1]."), (1, "See Figure 1-1 again.")]
    # empty printed number on the first pages is NULL; the figure text is the evaluated figure document
    assert db.execute("SELECT pdf_index, printed_number FROM pages ORDER BY pdf_index").fetchall() == \
        [(1, None), (2, None), (3, "1-1"), (4, "1-2"), (5, "2-1")]
    text = scalar(db, "SELECT search_text FROM figures WHERE figure_number = '1-1'")
    assert text.startswith("Intro > ") is False and "Figure 1-1. Airspace." in text and "See Figure 1-1 again." in text
    chunk = db.execute("SELECT heading_path, pdf_pages, printed_pages, figure_mentions FROM chunks "
                       f"WHERE chunk_id = '{HID}-c0001'").fetchone()
    assert chunk == (["Intro"], [3], ["1-1"], ["1-1"])


def test_image_paths_are_relative_keys_never_absolute(db, root):
    load_db.load(db, sources(root))
    for (path,) in db.execute("SELECT image_path FROM figures"):
        assert path.startswith(f"{HID}/figures/")
        assert ":" not in path and not path.startswith(("/", "\\")) and ".." not in path
        assert str(root) not in path


@pytest.mark.parametrize("bad", ["/etc/x.png", "C:/data/x.png", "../x.png", "figures/../../x.png", "\\server\\x.png"])
def test_absolute_or_parent_image_paths_are_refused(bad):
    with pytest.raises(load_db.LoadError, match="relative"):
        load_db.relative_key(HID, bad)


# --- re-run, resume, reset ----------------------------------------------------------------

def test_running_again_does_not_duplicate_anything(db, root):
    load_db.load(db, sources(root))
    ids = db.execute("SELECT id FROM figures ORDER BY id").fetchall()
    db.commit()
    assert load_db.load(db, sources(root)) == WANT
    assert load_db.database_counts(db, HID) == WANT
    assert db.execute("SELECT id FROM figures ORDER BY id").fetchall() == ids  # not deleted and re-inserted
    assert status(db) == ("loaded", True)


def test_a_failed_load_stays_not_searchable_and_can_be_resumed(db, root):
    folder = root / "data" / "extracted" / HID
    good = (folder / "figures.jsonl").read_text(encoding="utf-8")
    figures = [json.loads(line) for line in good.splitlines()]
    figures[1]["referencing_paragraphs"][0]["pdf_page"] = None   # NOT NULL violation, found only by the database
    write_jsonl(folder / "figures.jsonl", figures)

    with pytest.raises(Exception):
        load_db.load(db, sources(root))
    assert status(db) == ("failed", False)
    assert visible(db) == (0, 0)
    # the work done before the error is kept (figures, pages) ...
    assert load_db.database_counts(db, HID)["figures"] == 3

    (folder / "figures.jsonl").write_text(good, encoding="utf-8")  # ... so after the fix the run continues
    assert load_db.load(db, sources(root)) == WANT
    assert status(db) == ("loaded", True)
    assert visible(db) == (3, 4)


def test_batches_before_a_failing_batch_are_kept_so_the_run_can_continue(db, root, monkeypatch):
    monkeypatch.setattr(load_db, "BATCH", 1)            # one row per batch: 4 chunk batches
    folder = root / "data" / "extracted" / HID
    good = (folder / "chunks.jsonl").read_text(encoding="utf-8")
    chunks = [json.loads(line) for line in good.splitlines()]
    chunks[2]["words"] = None                           # third chunk: NOT NULL violation
    write_jsonl(folder / "chunks.jsonl", chunks)

    with pytest.raises(Exception):
        load_db.load(db, sources(root))
    assert status(db) == ("failed", False)
    assert load_db.database_counts(db, HID)["chunks"] == 2    # the two batches before the error were committed

    (folder / "chunks.jsonl").write_text(good, encoding="utf-8")
    assert load_db.load(db, sources(root)) == WANT


def test_count_mismatch_sets_failed(db, root):
    load_db.load(db, sources(root))
    db.execute("INSERT INTO chunks (document_id, chunk_id, chapter, heading_path, text, embed_text, words, "
               "pdf_pages, printed_pages, embedding) VALUES (%s, 'stale', '1', '{}', 't', 't', 1, '{}', '{}', %s)",
               (HID, np.zeros(384, dtype=np.float32).tolist()))
    db.commit()
    with pytest.raises(load_db.LoadError, match="row counts differ"):
        load_db.load(db, sources(root))      # the extra row is not in the files
    assert status(db) == ("failed", False)
    assert visible(db) == (0, 0)


def test_reset_deletes_the_old_rows_and_loads_again(db, root):
    folder = root / "data" / "extracted" / HID
    load_db.load(db, sources(root))
    figures = [json.loads(line) for line in (folder / "figures.jsonl").read_text(encoding="utf-8").splitlines()]
    figures[0]["caption"] = "Figure 1-1. CHANGED."
    write_jsonl(folder / "figures.jsonl", figures)

    load_db.load(db, sources(root))                        # without --reset existing rows are kept as they are
    assert scalar(db, "SELECT caption FROM figures WHERE figure_number = '1-1'") == "Figure 1-1. Airspace."

    old_ids = db.execute("SELECT id FROM figures").fetchall()
    db.commit()
    assert load_db.load(db, sources(root), reset=True) == WANT
    assert scalar(db, "SELECT caption FROM figures WHERE figure_number = '1-1'") == "Figure 1-1. CHANGED."
    assert db.execute("SELECT id FROM figures").fetchall() != old_ids   # really deleted and inserted again
    assert status(db) == ("loaded", True)


def test_reset_only_touches_this_handbook(db, root):
    load_db.load(db, sources(root))
    db.execute("INSERT INTO documents (id, title, source_url, licence, retrieved_at, embedding_model, status) "
               "VALUES ('OTHER', 'o', 'u', 'PD', now(), 'm', 'loaded')")
    db.commit()
    load_db.load(db, sources(root), reset=True)
    assert scalar(db, "SELECT count(*) FROM documents WHERE id = 'OTHER'") == 1


# --- licence (BR-001) ---------------------------------------------------------------------

@pytest.mark.parametrize("licence", ["", "unknown", "Unknown", "  UNKNOWN  ", "   "])
def test_unknown_licence_is_stored_as_null_and_is_not_searchable(db, tmp_path, licence):
    make_handbook(tmp_path, licence=licence)
    assert load_db.load(db, sources(tmp_path)) == WANT           # everything is loaded ...
    assert scalar(db, "SELECT licence FROM documents") is None
    assert status(db) == ("loaded", False)                       # ... but not searchable
    assert visible(db) == (0, 0)


def test_setting_the_licence_and_loading_again_makes_it_searchable(db, tmp_path):
    make_handbook(tmp_path, licence="")
    load_db.load(db, sources(tmp_path))
    assert visible(db) == (0, 0)
    (tmp_path / "corpus" / "handbooks.csv").write_text(
        f"id,title,url,licence\n{HID},Test Handbook,https://example.org/test.pdf,Public domain\n", encoding="utf-8")
    load_db.load(db, sources(tmp_path))
    assert visible(db) == (3, 4)


@pytest.mark.parametrize("value, expected", [(None, None), ("", None), ("unknown", None), ("UnKnown", None),
                                             ("  ", None), ("Public domain", "Public domain"),
                                             (" Public domain ", "Public domain"), ("unknown licence x", "unknown licence x")])
def test_normalize_licence(value, expected):
    assert load_db.normalize_licence(value) == expected


def test_no_retrieval_date_is_refused(tmp_path):
    make_handbook(tmp_path, retrieved_at=None)
    with pytest.raises(load_db.LoadError, match="BR-001"):
        sources(tmp_path)


# --- the files must agree before the database is touched -----------------------------------

def test_refuses_when_the_figure_embeddings_have_a_different_row_count(db, root):
    folder = root / "data" / "extracted" / HID
    np.save(folder / f"figure_embeddings_full_{MODEL.replace('/', '_')}.npy", vectors(2, 1))   # 2 rows, 3 figures
    with pytest.raises(load_db.LoadError, match="2 rows but the figures.jsonl file has 3"):
        sources(root)
    assert scalar(db, "SELECT count(*) FROM documents") == 0


def test_refuses_when_the_chunk_embeddings_have_a_different_row_count(root):
    folder = root / "data" / "extracted" / HID
    np.save(folder / f"chunk_embeddings_{MODEL.replace('/', '_')}.npy", vectors(5, 2))         # 5 rows, 4 chunks
    with pytest.raises(load_db.LoadError, match="5 rows but the chunks.jsonl file has 4"):
        sources(root)


def test_refuses_vectors_of_the_wrong_size(root):
    folder = root / "data" / "extracted" / HID
    np.save(folder / f"chunk_embeddings_{MODEL.replace('/', '_')}.npy", np.zeros((4, 128), dtype=np.float32))
    with pytest.raises(load_db.LoadError, match="384"):
        sources(root)


def test_unknown_handbook_is_refused(root):
    with pytest.raises(load_db.LoadError, match="not listed"):
        load_db.read_sources("NOPE", MODEL, root)
