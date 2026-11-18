"""Re-embed one figure or re-index handbooks (P7-32; FR-008, UC-10, UC-04 "re-embed a figure when it is
corrected").

Usage (from the repository root, database running):
    python ingestion/reindex.py FAA-H-8083-15B      # every figure of one handbook
    python ingestion/reindex.py ALL                 # every figure of every handbook

What is rebuilt: the vectors of the figure documents (figures.search_text), the text the live search
compares the question with: bge-small (figures.embedding, also the fallback) and, when EMBEDDING_MODEL
is an API model, that model (figure_text_embeddings). The text itself is the stored one, so a caption
corrected by an admin is searched with its new wording. Chunks are not re-embedded: they are not
corrected by the admin and are not used by the live "text" mode.

UC-10 A1: every vector is computed BEFORE anything is written, then all are written in ONE transaction.
If a computation fails (API quota, network), nothing is written and the previous index stays active.
"""
import sys
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ingestion"))
from backend import embedding  # noqa: E402
from migrate import connection_string  # noqa: E402

ALL = "ALL"


def local_vectors(texts):
    """bge-small vectors of figure documents: same call as evaluation/figure_retrieval.py embed (no prefix)."""
    from backend import retrieval
    return retrieval._model().encode(texts, batch_size=32, normalize_embeddings=True)


def figures_of(conn, handbook_id=None, figure_id=None):
    if figure_id is not None:
        return conn.execute("SELECT id, search_text FROM figures WHERE id = %s", (figure_id,)).fetchall()
    if handbook_id in (None, ALL):
        return conn.execute("SELECT id, search_text FROM figures ORDER BY id").fetchall()
    return conn.execute("SELECT id, search_text FROM figures WHERE document_id = %s ORDER BY id",
                        (handbook_id,)).fetchall()


def rebuild(conn, rows, model=None, local=local_vectors, api=embedding.embed_api):
    """Compute every vector of rows [(figure id, text)], then write them in one transaction.
    Returns the number of figures. Raises (and writes nothing) if a computation fails."""
    if not rows:
        return 0
    model = model or embedding.configured_model()
    ids, texts = [r[0] for r in rows], [r[1] for r in rows]
    bge = local(texts)
    api_vectors = api(model, texts, "document") if embedding.is_api_model(model) else None
    with conn.transaction():
        for i, fid in enumerate(ids):
            conn.execute("UPDATE figures SET embedding = %s WHERE id = %s", (bge[i], fid))
            if api_vectors is not None:
                conn.execute("""INSERT INTO figure_text_embeddings (figure_id, model, embedding) VALUES (%s, %s, %s)
                                ON CONFLICT (figure_id, model) DO UPDATE
                                SET embedding = EXCLUDED.embedding, embedded_at = now()""",
                             (fid, model, api_vectors[i]))
    return len(ids)


def reembed_figure(conn, figure_id, **kw):
    """After an admin corrects a figure (UC-04): its vectors from its current search_text. 0 if unknown."""
    return rebuild(conn, figures_of(conn, figure_id=figure_id), **kw)


def reindex(conn, handbook_id=ALL, **kw):
    """Every figure of one handbook, or of all of them (handbook_id "ALL")."""
    return rebuild(conn, figures_of(conn, handbook_id), **kw)


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python ingestion/reindex.py <handbook-id>|ALL")
    with psycopg.connect(connection_string()) as conn:
        register_vector(conn)
        done = reindex(conn, sys.argv[1])
    if done == 0:
        sys.exit(f"no figure found for {sys.argv[1]}")
    print(f"Re-indexed {done} figures ({sys.argv[1]}) with {embedding.configured_model()}")


if __name__ == "__main__":
    main()
