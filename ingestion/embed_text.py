"""Embed the figure documents (and optionally the chunks) with an API model (P7-57).

Usage (from the repository root, database running, migration 010 applied, key in .env):
    python ingestion/embed_text.py gemini-embedding-001             # figures not embedded yet
    python ingestion/embed_text.py text-embedding-3-small --chunks  # also the chunks (passages mode)
    python ingestion/embed_text.py gemini-embedding-001 --all       # recompute everything

The text embedded is exactly the text bge-small embedded at loading time (figures.search_text =
caption + citing paragraph, chunks.embed_text = heading + text), so the comparison between models
is fair: only the model changes. The live "text" search needs the figures only; the chunks are only
used by the "passages" and "hybrid" modes. Resumable: stopped halfway (quota, network), run it again
and it continues where it stopped; every batch is committed.
"""
import argparse
import sys
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ingestion"))
from backend.embedding import MODELS, embed_api, is_api_model  # noqa: E402
from migrate import connection_string  # noqa: E402

BATCH = 100

TARGETS = {
    # name: (SELECT of the rows to embed, INSERT)
    "figures": ("""SELECT f.id, f.search_text FROM figures f
                   WHERE %(all)s OR NOT EXISTS (SELECT 1 FROM figure_text_embeddings e
                                                WHERE e.figure_id = f.id AND e.model = %(model)s)
                   ORDER BY f.id""",
                """INSERT INTO figure_text_embeddings (figure_id, model, embedding) VALUES (%s, %s, %s)
                   ON CONFLICT (figure_id, model) DO UPDATE
                   SET embedding = EXCLUDED.embedding, embedded_at = now()"""),
    "chunks": ("""SELECT c.id, c.embed_text FROM chunks c
                  WHERE %(all)s OR NOT EXISTS (SELECT 1 FROM chunk_text_embeddings e
                                               WHERE e.chunk_id = c.id AND e.model = %(model)s)
                  ORDER BY c.id""",
               """INSERT INTO chunk_text_embeddings (chunk_id, model, embedding) VALUES (%s, %s, %s)
                  ON CONFLICT (chunk_id, model) DO UPDATE
                  SET embedding = EXCLUDED.embedding, embedded_at = now()"""),
}


def embed_target(conn, target, model, redo_all=False, embed=embed_api, batch=BATCH, report=print):
    """Embed the rows of one target ("figures" or "chunks"). Returns how many were embedded.
    embed(model, texts, kind) -> vectors can be replaced (tests use a fake)."""
    select, insert = TARGETS[target]
    rows = conn.execute(select, {"all": redo_all, "model": model}).fetchall()
    done = 0
    for start in range(0, len(rows), batch):
        part = rows[start:start + batch]
        vectors = embed(model, [text for _id, text in part], "document")
        with conn.transaction():
            for (row_id, _text), vector in zip(part, vectors):
                conn.execute(insert, (row_id, model, vector))
        done += len(part)
        report(f"  {target}: {done}/{len(rows)}")
    return done


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", choices=[m for m in MODELS if is_api_model(m)])
    parser.add_argument("--chunks", action="store_true", help="also embed the chunks")
    parser.add_argument("--all", action="store_true", help="recompute rows already embedded")
    args = parser.parse_args()
    with psycopg.connect(connection_string(), autocommit=True) as conn:
        register_vector(conn)
        for target in ["figures"] + (["chunks"] if args.chunks else []):
            embed_target(conn, target, args.model, args.all)
        figures = conn.execute("SELECT count(*) FROM figures").fetchone()[0]
        done = conn.execute("SELECT count(*) FROM figure_text_embeddings WHERE model = %s",
                            (args.model,)).fetchone()[0]
    print(f"Figures with a {args.model} embedding: {done} of {figures}")


if __name__ == "__main__":
    main()
