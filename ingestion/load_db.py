"""Load one extracted handbook into PostgreSQL (tables of db/migrations/001_init.sql).

Usage (from the repository root; database running and migrated):
    python ingestion/migrate.py
    python ingestion/load_db.py FAA-H-8083-15B
    python ingestion/load_db.py FAA-H-8083-15B --reset      # delete this handbook's rows first

It reads, for the handbook given on the command line:
    corpus/handbooks.csv                          title, source URL, licence
    data/raw/<id>.meta.json                       retrieval date, sha256, size
    data/inspect/<id>_pages.csv                   PDF page -> printed page number
    data/extracted/<id>/figures.jsonl, chunks.jsonl, report.json
    data/extracted/<id>/figure_embeddings_full_<model>.npy, chunk_embeddings_<model>.npy

Order: the documents row first (status 'loading'), then pages, figures, figure_refs
and chunks in batches (each batch is committed), then the row counts in the database
are compared with the files. Only if they are equal is the status set to 'loaded';
on a mismatch or an error it is set to 'failed'. A document that is not 'loaded', or
whose licence is unknown, is never searchable (the searchable_* views).

Safe to re-run: rows are inserted with ON CONFLICT DO NOTHING on their natural keys
(handbook + figure number, + chunk id, + page), so a run that stopped half-way is
continued, not duplicated. Rows that already exist are NOT updated: if the extracted
files changed, use --reset.

Images and PDFs are not loaded. image_path is a relative key such as
FAA-H-8083-15B/figures/4-12.png.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from migrate import connection_string

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))
# Reused, not copied: the figure-document text is the one that was embedded and evaluated.
from baseline_retrieval import slug  # noqa: E402
from figure_retrieval import build_documents  # noqa: E402

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384  # vector(384) in 001_init.sql
BATCH = 200


class LoadError(Exception):
    """The files or the database are not in a state we can load from."""


def normalize_licence(value):
    """Empty or "unknown" (any case) means the licence is not known: NULL."""
    if value is None:
        return None
    value = value.strip()
    return None if value == "" or value.lower() == "unknown" else value


def read_jsonl(path):
    if not path.exists():
        raise LoadError(f"{path} not found")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def relative_key(handbook_id, image_path):
    """FAA-H-8083-15B/figures/4-12.png from figures/4-12.png; never absolute, never '..'."""
    p = Path(image_path)
    if p.is_absolute() or image_path.startswith(("/", "\\")) or ".." in p.parts or p.drive:
        raise LoadError(f"image path must be relative, got {image_path!r}")
    return f"{handbook_id}/{p.as_posix()}"


def read_vectors(path, rows, what):
    if not path.exists():
        raise LoadError(f"{path} not found")
    vectors = np.load(path)
    if vectors.ndim != 2 or vectors.shape[1] != DIMENSIONS:
        raise LoadError(f"{path.name}: expected {DIMENSIONS} columns, got shape {vectors.shape}")
    if len(vectors) != rows:
        raise LoadError(f"{path.name} has {len(vectors)} rows but the {what} file has {rows}; "
                        "embed again before loading")
    return vectors.astype(np.float32)


def read_sources(handbook_id, model=DEFAULT_MODEL, root=ROOT):
    """Everything to load, checked. Raises LoadError before the database is touched."""
    root = Path(root)
    row = None
    handbooks = root / "corpus" / "handbooks.csv"
    if not handbooks.exists():
        raise LoadError(f"{handbooks} not found")
    with open(handbooks, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["id"] == handbook_id:
                row = r
    if row is None:
        raise LoadError(f"{handbook_id} is not listed in corpus/handbooks.csv")

    meta_path = root / "data" / "raw" / f"{handbook_id}.meta.json"
    if not meta_path.exists():
        raise LoadError(f"{meta_path} not found: the retrieval date is required (BR-001)")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not row.get("url") or not meta.get("retrieved_at"):
        raise LoadError("source URL and retrieval date are required (BR-001)")

    folder = root / "data" / "extracted" / handbook_id
    figures = read_jsonl(folder / "figures.jsonl")
    chunks = read_jsonl(folder / "chunks.jsonl")
    figure_vectors = read_vectors(folder / f"figure_embeddings_full_{slug(model)}.npy", len(figures), "figures.jsonl")
    chunk_vectors = read_vectors(folder / f"chunk_embeddings_{slug(model)}.npy", len(chunks), "chunks.jsonl")

    pages = []
    pages_path = root / "data" / "inspect" / f"{handbook_id}_pages.csv"
    if not pages_path.exists():
        raise LoadError(f"{pages_path} not found: run ingestion/inspect_pdf.py first")
    with open(pages_path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            pages.append((int(r["pdf_page"]), r["printed_page"].strip() or None))

    report_path = folder / "report.json"
    pdf_pages = json.loads(report_path.read_text(encoding="utf-8")).get("pdf_pages") if report_path.exists() else None

    search_texts = [d["embed_text"] for d in build_documents(figures, chunks)]
    keys = [relative_key(handbook_id, f["image_path"]) for f in figures]
    return {
        "document": {
            "id": handbook_id, "title": row["title"], "source_url": row["url"],
            "licence": normalize_licence(row.get("licence")), "retrieved_at": meta["retrieved_at"],
            "sha256": meta.get("sha256"), "bytes": meta.get("bytes"),
            "pdf_pages": pdf_pages, "embedding_model": model,
        },
        "pages": pages, "figures": figures, "chunks": chunks,
        "figure_vectors": figure_vectors, "chunk_vectors": chunk_vectors,
        "search_texts": search_texts, "image_keys": keys,
    }


def batches(items, size=None):
    size = size or BATCH   # read when called, so tests can make it small
    for i in range(0, len(items), size):
        yield items[i:i + size]


def expected_counts(src):
    return {"pages": len(src["pages"]), "figures": len(src["figures"]),
            "figure_refs": sum(len(f["referencing_paragraphs"]) for f in src["figures"]),
            "chunks": len(src["chunks"])}


def database_counts(conn, handbook_id):
    with conn.cursor() as cur:
        cur.execute("""SELECT
            (SELECT count(*) FROM pages  WHERE document_id = %(d)s),
            (SELECT count(*) FROM figures WHERE document_id = %(d)s),
            (SELECT count(*) FROM figure_refs r JOIN figures f ON f.id = r.figure_id WHERE f.document_id = %(d)s),
            (SELECT count(*) FROM chunks WHERE document_id = %(d)s)""", {"d": handbook_id})
        pages, figures, refs, chunks = cur.fetchone()
    conn.commit()
    return {"pages": pages, "figures": figures, "figure_refs": refs, "chunks": chunks}


def insert_rows(conn, sql, rows):
    with conn.cursor() as cur:
        for batch in batches(rows):
            cur.executemany(sql, batch)
            conn.commit()  # each batch is kept even if a later one fails: the run can be resumed


def load(conn, src, reset=False):
    """Load checked sources; return the row counts. Sets status 'loaded' or 'failed'."""
    d = src["document"]
    hid = d["id"]
    register_vector(conn)
    if reset:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (hid,))  # cascades to every table
        conn.commit()
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO documents (id, title, source_url, licence, retrieved_at, sha256, bytes,
                                              pdf_pages, embedding_model, status, loaded_at)
                       VALUES (%(id)s, %(title)s, %(source_url)s, %(licence)s, %(retrieved_at)s, %(sha256)s,
                               %(bytes)s, %(pdf_pages)s, %(embedding_model)s, 'loading', NULL)
                       ON CONFLICT (id) DO UPDATE SET
                           title = EXCLUDED.title, source_url = EXCLUDED.source_url, licence = EXCLUDED.licence,
                           retrieved_at = EXCLUDED.retrieved_at, sha256 = EXCLUDED.sha256, bytes = EXCLUDED.bytes,
                           pdf_pages = EXCLUDED.pdf_pages, embedding_model = EXCLUDED.embedding_model,
                           status = 'loading', loaded_at = NULL""", d)
    conn.commit()
    try:
        insert_rows(conn, """INSERT INTO pages (document_id, pdf_index, printed_number) VALUES (%s, %s, %s)
                             ON CONFLICT (document_id, pdf_index) DO NOTHING""",
                    [(hid, pdf, printed) for pdf, printed in src["pages"]])

        figure_rows = []
        for f, vector, text, key in zip(src["figures"], src["figure_vectors"], src["search_texts"], src["image_keys"]):
            figure_rows.append((hid, f["figure_number"], f["caption"], f["pdf_page"], f["printed_page"], f["status"],
                                "needs_review" in f, f.get("rotation", 0), f.get("bbox"), f.get("caption_bbox"),
                                key, text, vector))
        insert_rows(conn, """INSERT INTO figures (document_id, figure_number, caption, pdf_page, printed_page, status,
                                                  needs_review, rotation, bbox, caption_bbox, image_path,
                                                  search_text, embedding)
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                             ON CONFLICT (document_id, figure_number) DO NOTHING""", figure_rows)

        with conn.cursor() as cur:
            cur.execute("SELECT figure_number, id FROM figures WHERE document_id = %s", (hid,))
            ids = dict(cur.fetchall())
        conn.commit()
        ref_rows = [(ids[f["figure_number"]], position, r["pdf_page"], r["printed_page"], r["text"])
                    for f in src["figures"] for position, r in enumerate(f["referencing_paragraphs"])]
        insert_rows(conn, """INSERT INTO figure_refs (figure_id, position, pdf_page, printed_page, text)
                             VALUES (%s, %s, %s, %s, %s)
                             ON CONFLICT (figure_id, position) DO NOTHING""", ref_rows)

        chunk_rows = [(hid, c["chunk_id"], c["chapter"], c["heading_path"], c["text"], c["embed_text"], c["words"],
                       c["pdf_pages"], c["printed_pages"], c["figure_mentions"], vector)
                      for c, vector in zip(src["chunks"], src["chunk_vectors"])]
        insert_rows(conn, """INSERT INTO chunks (document_id, chunk_id, chapter, heading_path, text, embed_text, words,
                                                 pdf_pages, printed_pages, figure_mentions, embedding)
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                             ON CONFLICT (document_id, chunk_id) DO NOTHING""", chunk_rows)

        want, have = expected_counts(src), database_counts(conn, hid)
        if want != have:
            raise LoadError(f"row counts differ: files {want}, database {have}")
        with conn.cursor() as cur:
            cur.execute("UPDATE documents SET status = 'loaded', loaded_at = now() WHERE id = %s", (hid,))
        conn.commit()
        return have
    except BaseException:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("UPDATE documents SET status = 'failed', loaded_at = NULL WHERE id = %s", (hid,))
        conn.commit()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load one extracted handbook into PostgreSQL.")
    parser.add_argument("handbook_id")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="embedding model the .npy files were made with")
    parser.add_argument("--reset", action="store_true", help="delete this handbook's rows and load from scratch")
    args = parser.parse_args(argv)
    try:
        src = read_sources(args.handbook_id, args.model)
        with psycopg.connect(connection_string()) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('documents')")
                if cur.fetchone()[0] is None:
                    raise LoadError("the tables do not exist: run python ingestion/migrate.py first")
            conn.commit()
            counts = load(conn, src, reset=args.reset)
            with conn.cursor() as cur:
                cur.execute("SELECT status, searchable FROM documents WHERE id = %s", (args.handbook_id,))
                status, searchable = cur.fetchone()
    except LoadError as exc:
        sys.exit(f"load failed: {exc}")
    except psycopg.Error as exc:
        sys.exit(f"load failed (database): {exc}")
    print(f"{args.handbook_id}: status {status}, searchable {searchable}")
    for name, n in counts.items():
        print(f"  {name:12} {n}")
    if not searchable:
        print("  NOT searchable: the licence is unknown (set it in corpus/handbooks.csv and load again).")


if __name__ == "__main__":
    main()
