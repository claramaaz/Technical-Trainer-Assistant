"""Search over the figure documents (baseline v2, SPEC 5.1), no database.

retrieve(query, k) embeds the question with the same model and query prefix as
evaluation/figure_retrieval.py, ranks the figure documents by cosine similarity
and returns the top k, or an empty result when the best score is too low.

All data access is in load_index(). It is the ONLY function that reads files
(figures.jsonl, chunks.jsonl, the embeddings, the handbook name). When the
pgvector database is ready, replace load_index() (and rank(), which does the
dot product) and nothing else has to change.

Paths are built from this file's location, so it works from any directory.
"""
import csv
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evaluation"))
# Reused, not copied: the document text, the heading rule and the query prefix are
# exactly the ones that were evaluated.
from baseline_retrieval import QUERY_PREFIX, load_model  # noqa: E402
from figure_retrieval import build_documents, load_jsonl, paths  # noqa: E402

HANDBOOK_ID = "FAA-H-8083-15B"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

# PROVISIONAL. Chosen by looking at the scores of the same 23 answerable questions
# and 2 no-answer questions (Q001-Q025) that it is then tested on, so it is NOT
# validated. The margin is tiny: Q017's correct top-1 scores 0.653, Q025 (no answer)
# scores 0.626. Must be re-set on a separate set with more no-answer questions.
THRESHOLD = 0.65

NO_ANSWER = "no_adequate_answer"


@dataclass
class Index:
    documents: list      # one dict per figure: figure_number, caption, image_path, passage, printed_page
    vectors: np.ndarray  # normalized, row i = documents[i]
    handbook: str


def handbook_title(handbook_id):
    with open(ROOT / "corpus" / "handbooks.csv", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row["id"] == handbook_id:
                return row["title"]
    return handbook_id


@lru_cache(maxsize=1)
def load_index():
    """Read all data from the files. Replace this function when moving to pgvector."""
    folder = ROOT / "data" / "extracted" / HANDBOOK_ID
    figures = load_jsonl(folder / "figures.jsonl", "run ingestion/extract_figures.py first.")
    chunks = load_jsonl(folder / "chunks.jsonl", "run ingestion/chunk_text.py chunk first.")
    emb_path = ROOT / paths(HANDBOOK_ID, MODEL_NAME, "full")[2]
    if not emb_path.exists():
        raise FileNotFoundError(f"{emb_path} not found: run evaluation/figure_retrieval.py embed first.")
    vectors = np.load(emb_path)
    if len(vectors) != len(figures):
        raise ValueError(f"{emb_path.name} has {len(vectors)} rows but figures.jsonl has {len(figures)} figures")
    # Same figure order as the embeddings (row i = line i of figures.jsonl); the
    # evaluated document text is reused, not rebuilt, by build_documents.
    docs = build_documents(figures, chunks)
    documents = []
    for f, doc in zip(figures, docs):
        refs = f["referencing_paragraphs"]
        documents.append({
            "figure_number": doc["figure_number"],
            "caption": f["caption"],
            "image_path": folder / f["image_path"],
            "passage": refs[0]["text"] if refs else "",
            "printed_page": f["printed_page"],
        })
    return Index(documents, vectors, handbook_title(HANDBOOK_ID))


@lru_cache(maxsize=1)
def _model():
    return load_model(MODEL_NAME)


def embed_query(query):
    return _model().encode([QUERY_PREFIX + query], normalize_embeddings=True)[0]


def rank(index, query_vector, k):
    """(row, score) of the k best documents, best first."""
    scores = index.vectors @ query_vector
    order = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in order]


def retrieve(query, k=5, index=None, query_vector=None):
    """Top-k figures for a question, or {"results": [], "reason": "no_adequate_answer"}.

    index and query_vector can be passed in (tests do); by default they are loaded.
    """
    index = index or load_index()
    if query_vector is None:
        query_vector = embed_query(query)
    ranked = rank(index, query_vector, k)
    if not ranked or ranked[0][1] < THRESHOLD:
        return {"results": [], "reason": NO_ANSWER}
    results = []
    for i, score in ranked:
        d = index.documents[i]
        results.append({
            "figure_id": d["figure_number"],
            "caption": d["caption"],
            "image_path": str(d["image_path"]),
            "image_url": f"/figures/{d['figure_number']}/image",
            "passage": d["passage"],
            "handbook": index.handbook,
            "printed_page": d["printed_page"],
            "score": score,
        })
    return {"results": results, "reason": None}


def image_path_for(figure_id):
    """Image file of a figure, or None if the id is not in the index (never built from user text)."""
    for d in load_index().documents:
        if d["figure_number"] == figure_id:
            return d["image_path"] if d["image_path"].is_file() else None
    return None
