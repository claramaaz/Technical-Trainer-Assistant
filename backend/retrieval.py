"""Search over the figure documents (baseline v2, SPEC 5.1), reading from PostgreSQL.

retrieve(query, k) embeds the question with the same model and query prefix as
evaluation/figure_retrieval.py, asks the database for the k figures nearest to it and
returns them, or an empty result when the best score is too low.

All data access is in load_index() (descriptions of the figures) and rank() (the
nearest-neighbour query). They read ONLY the views searchable_figures and
searchable_figure_refs, never the tables, so a document with an unknown licence, or
one that is not fully loaded, can never be returned (BR-001). There is no file-based
fallback any more.

Connection: POSTGRES_* variables from the environment or .env, host 127.0.0.1 (the
same code as ingestion/migrate.py and the loader).
"""
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))
sys.path.insert(0, str(ROOT / "ingestion"))
# Reused, not copied: the query prefix is the one that was evaluated, and the
# connection settings are the ones the loader uses.
from baseline_retrieval import QUERY_PREFIX, load_model  # noqa: E402
from migrate import connection_string  # noqa: E402

MODEL_NAME = "BAAI/bge-small-en-v1.5"

# PROVISIONAL. Chosen by looking at the scores of the same 23 answerable questions
# and 2 no-answer questions (Q001-Q025) that it is then tested on, so it is NOT
# validated. The margin is tiny: Q017's correct top-1 scores 0.653, Q025 (no answer)
# scores 0.626. Must be re-set on a separate set with more no-answer questions.
THRESHOLD = 0.65

NO_ANSWER = "no_adequate_answer"


@dataclass
class Index:
    # database figure id -> dict: figure_number, caption, image_path, passage, printed_page,
    # handbook_id, handbook (title). Provenance is per figure: one index holds several handbooks.
    documents: dict
    dsn: str         # how rank() reaches the database


# One row per searchable figure; the passage is the first citing paragraph (position 0).
DESCRIBE_SQL = """
    SELECT f.id, f.figure_number, f.caption, f.image_path, f.printed_page, f.handbook, f.document_id,
           (SELECT r.text FROM searchable_figure_refs r WHERE r.figure_id = f.id AND r.position = 0)
    FROM searchable_figures f
    ORDER BY f.id"""

# Score = 1 - cosine distance. The id breaks ties so the order is always the same.
# handbooks = a list of document ids such as ["FAA-H-8083-15B"], or NULL for all handbooks.
RANK_SQL = """
    SELECT id, 1 - (embedding <=> %(q)s) AS score
    FROM searchable_figures
    WHERE %(handbooks)s::text[] IS NULL OR document_id = ANY(%(handbooks)s::text[])
    ORDER BY embedding <=> %(q)s, id
    LIMIT %(k)s"""


def connect(dsn):
    conn = psycopg.connect(dsn)
    register_vector(conn)
    return conn


def load_index_from(dsn):
    """Describe every searchable figure (no vectors: the database does the ranking)."""
    with connect(dsn) as conn:
        rows = conn.execute(DESCRIBE_SQL).fetchall()
    documents = {}
    for fid, number, caption, image_key, printed_page, handbook, handbook_id, passage in rows:
        documents[fid] = {
            "figure_number": number,
            "caption": caption,
            # image_path is a relative key such as FAA-H-8083-15B/figures/4-12.png
            "image_path": ROOT / "data" / "extracted" / image_key,
            "passage": passage or "",
            "printed_page": printed_page,
            "handbook_id": handbook_id,
            "handbook": handbook,
        }
    return Index(documents, dsn)


@lru_cache(maxsize=1)
def load_index():
    """The index for the configured database. Read once; restart after loading a new handbook."""
    return load_index_from(connection_string())


@lru_cache(maxsize=1)
def _model():
    return load_model(MODEL_NAME)


def embed_query(query):
    return _model().encode([QUERY_PREFIX + query], normalize_embeddings=True)[0]


def rank(index, query_vector, k, handbooks=None):
    """(figure id, score) of the k best searchable figures, best first. Done by the database.

    handbooks: optional list of handbook (document) ids to search in; None = all handbooks."""
    handbooks = list(handbooks) if handbooks is not None else None
    with connect(index.dsn) as conn:
        rows = conn.execute(RANK_SQL, {"q": query_vector, "k": k, "handbooks": handbooks}).fetchall()
    return [(int(fid), float(score)) for fid, score in rows]


def retrieve(query, k=5, index=None, query_vector=None, handbooks=None):
    """Top-k figures for a question, or {"results": [], "reason": "no_adequate_answer"}.

    handbooks: optional list of handbook ids to search in (default None = all handbooks). The
    threshold is applied to the best score inside that selection.

    index and query_vector can be passed in (tests do); by default they are loaded.
    """
    index = index or load_index()
    if query_vector is None:
        query_vector = embed_query(query)
    ranked = rank(index, query_vector, k, handbooks)
    if not ranked or ranked[0][1] < THRESHOLD:
        return {"results": [], "reason": NO_ANSWER}
    results = []
    for i, score in ranked:
        d = index.documents[i]
        results.append({
            "id": i,                           # database id: unique across handbooks, the stable id
            "figure_id": d["figure_number"],   # printed number ("3-1"), for display only
            "caption": d["caption"],
            "image_url": f"/figures/{i}/image",
            "passage": d["passage"],
            "handbook_id": d["handbook_id"],
            "handbook": d["handbook"],
            "printed_page": d["printed_page"],
            "score": score,
        })
    return {"results": results, "reason": None}


def image_path_for(figure_id):
    """Image file of a figure by DATABASE id, or None if the id is not in the index.

    The printed number ("3-1") is not an id: it exists in every handbook. The path comes from the
    index, never from the text of the URL."""
    if isinstance(figure_id, str) and figure_id.isascii() and figure_id.isdigit():
        figure_id = int(figure_id)
    if not isinstance(figure_id, int) or isinstance(figure_id, bool):
        return None
    d = load_index().documents.get(figure_id)
    return d["image_path"] if d and d["image_path"].is_file() else None
