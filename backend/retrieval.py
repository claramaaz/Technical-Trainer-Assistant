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

Joint text + image retrieval (P7-30, brief section 4). RETRIEVAL_MODE (environment or .env) chooses
how the figures are ranked:
    text  = the text search above (bge-small on caption + citing paragraph). Default.
    image = CLIP: the question is compared with the figure IMAGE (ingestion/embed_images.py).
    joint = both lists fused with Reciprocal Rank Fusion (fuse_rrf()).
    passages = figures found through the PASSAGES of the handbook (chunks): the question is compared
               with every chunk, and a chunk that mentions "Figure 3-3" gives its score to figure 3-3.
    hybrid   = the text list and the passages list fused with RRF (SRS UC-02 step 3: the system
               searches the stored text and figures together).
In every mode the "no answer" decision and the confidence use the TEXT similarity of the best text
match, the score the thresholds were set on: the image score of CLIP is on another scale.
"""
import os
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
from migrate import connection_string, read_env_file  # noqa: E402

MODEL_NAME = "BAAI/bge-small-en-v1.5"

# P7-30. Same name as ingestion/embed_images.py: the question and the images must use one model.
IMAGE_MODEL_NAME = "clip-ViT-B-32"
MODES = ("text", "image", "joint", "passages", "hybrid")
DEFAULT_MODE = "text"
# Reciprocal Rank Fusion: score = sum over the lists of 1 / (RRF_K + rank). 60 is the value of the
# paper that introduced it (Cormack, Clarke and Buettcher, SIGIR 2009); not tuned on our questions.
RRF_K = 60
# How many figures each list gives to the fusion. A figure ranked 6th by text and 1st by image
# must still be able to reach the top 5, so the lists are longer than k.
CANDIDATES = 50
# How many chunks (passages) are read to build the passages list. Several chunks can cite the same
# figure, so the list of figures is shorter than this.
CHUNK_CANDIDATES = 100
# CLIP reads at most 77 tokens; a longer question would raise an error. Questions are short.
CLIP_MAX_WORDS = 50

# PROVISIONAL. Chosen by looking at the scores of the same 23 answerable questions
# and 2 no-answer questions (Q001-Q025) that it is then tested on, so it is NOT
# validated. The margin is tiny: Q017's correct top-1 scores 0.653, Q025 (no answer)
# scores 0.626. Must be re-set on a separate set with more no-answer questions.
THRESHOLD = 0.65

# PROVISIONAL, like THRESHOLD: a placeholder so the low-confidence notice can be built and tested
# (FR-002, UC-02 A3, brief section 12). Between THRESHOLD and this value the best figure is shown
# with confidence "low". To be set on the 50-question run and recorded in EVALUATION.md. On the
# 25-question run, Q017's correct top-1 scores 0.653 and Q025 (no answer) 0.626: the zone just
# above THRESHOLD is where the system cannot tell right from wrong.
LOW_CONFIDENCE_BELOW = 0.70

NO_ANSWER = "no_adequate_answer"


@dataclass
class Index:
    # database figure id -> dict: figure_number, caption, image_path, passage, printed_page,
    # handbook_id, handbook (title). Provenance is per figure: one index holds several handbooks.
    documents: dict
    dsn: str         # how rank() reaches the database


# One row per searchable figure; the passage is the first citing paragraph (position 0).
# The page the figure is on gives the stored page image and the source PDF link (UC-07, P7-47).
DESCRIBE_SQL = """
    SELECT f.id, f.figure_number, f.caption, f.image_path, f.printed_page, f.handbook, f.document_id,
           (SELECT r.text FROM searchable_figure_refs r WHERE r.figure_id = f.id AND r.position = 0),
           f.pdf_page, p.image_path, p.source_url, f.thumbnail_path
    FROM searchable_figures f
    LEFT JOIN searchable_pages p ON p.document_id = f.document_id AND p.pdf_index = f.pdf_page
    ORDER BY f.id"""

# Score = 1 - cosine distance. The id breaks ties so the order is always the same.
# handbooks = a list of document ids such as ["FAA-H-8083-15B"], or NULL for all handbooks.
RANK_SQL = """
    SELECT id, 1 - (embedding <=> %(q)s) AS score
    FROM searchable_figures
    WHERE %(handbooks)s::text[] IS NULL OR document_id = ANY(%(handbooks)s::text[])
    ORDER BY embedding <=> %(q)s, id
    LIMIT %(k)s"""

# Same as RANK_SQL, on the CLIP image vectors (P7-30). Reads the view, never the table (BR-001).
IMAGE_RANK_SQL = """
    SELECT id, 1 - (embedding <=> %(q)s) AS score
    FROM searchable_figure_images
    WHERE model = %(model)s
      AND (%(handbooks)s::text[] IS NULL OR document_id = ANY(%(handbooks)s::text[]))
    ORDER BY embedding <=> %(q)s, id
    LIMIT %(k)s"""

# The chunks nearest to the question that cite at least one figure (P7-30). Reads the view (BR-001).
# The question vector is the bge one, with the same query prefix: chunks were embedded with bge-small.
CHUNK_RANK_SQL = """
    SELECT document_id, figure_mentions, 1 - (embedding <=> %(q)s) AS score
    FROM searchable_chunks
    WHERE cardinality(figure_mentions) > 0
      AND (%(handbooks)s::text[] IS NULL OR document_id = ANY(%(handbooks)s::text[]))
    ORDER BY embedding <=> %(q)s, id
    LIMIT %(k)s"""

# Text similarity of given figures: a figure brought in by the image list only still needs its
# text score for the threshold and for display.
TEXT_SCORE_SQL = """
    SELECT id, 1 - (embedding <=> %(q)s) AS score
    FROM searchable_figures
    WHERE id = ANY(%(ids)s::bigint[])"""


def connect(dsn):
    conn = psycopg.connect(dsn)
    register_vector(conn)
    return conn


def load_index_from(dsn, image_root=None):
    """Describe every searchable figure (no vectors: the database does the ranking).

    image_root: folder of the image files (default data/extracted); tests pass their own."""
    image_root = Path(image_root) if image_root else ROOT / "data" / "extracted"
    with connect(dsn) as conn:
        rows = conn.execute(DESCRIBE_SQL).fetchall()
    documents = {}
    for (fid, number, caption, image_key, printed_page, handbook, handbook_id, passage,
         pdf_page, page_key, source_url, thumb_key) in rows:
        page_image = image_root / page_key if page_key else None
        thumbnail = image_root / thumb_key if thumb_key else None
        documents[fid] = {
            "figure_number": number,
            "caption": caption,
            # image_path is a relative key such as FAA-H-8083-15B/figures/4-12.png
            "image_path": image_root / image_key,
            "passage": passage or "",
            "printed_page": printed_page,
            "handbook_id": handbook_id,
            "handbook": handbook,
            "pdf_page": pdf_page,
            # None when the page was not rendered: "View source" then says so (UC-07 A1)
            "page_image_path": page_image if page_image and page_image.is_file() else None,
            "source_url": source_url,
            # NFR-001: small WebP shown first; None when make_thumbnails.py has not run
            "thumbnail_path": thumbnail if thumbnail and thumbnail.is_file() else None,
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


def retrieval_mode(environ=None, env_file=None):
    """RETRIEVAL_MODE from the environment, else .env, else "text". An unknown value stops."""
    environ = os.environ if environ is None else environ
    mode = environ.get("RETRIEVAL_MODE") or read_env_file(env_file or ROOT / ".env").get("RETRIEVAL_MODE")
    mode = (mode or DEFAULT_MODE).strip().lower()
    if mode not in MODES:
        raise ValueError(f"RETRIEVAL_MODE must be one of {MODES}, got {mode!r}")
    return mode


@lru_cache(maxsize=1)
def _image_model():
    return load_model(IMAGE_MODEL_NAME)


def embed_image_query(query):
    """The question as a CLIP vector (comparable with the figure images)."""
    words = query.split()[:CLIP_MAX_WORDS]
    return _image_model().encode([" ".join(words)], normalize_embeddings=True)[0]


def rank(index, query_vector, k, handbooks=None):
    """(figure id, score) of the k best searchable figures, best first. Done by the database.

    handbooks: optional list of handbook (document) ids to search in; None = all handbooks."""
    handbooks = list(handbooks) if handbooks is not None else None
    with connect(index.dsn) as conn:
        rows = conn.execute(RANK_SQL, {"q": query_vector, "k": k, "handbooks": handbooks}).fetchall()
    return [(int(fid), float(score)) for fid, score in rows]


def rank_image(index, image_query_vector, k, handbooks=None):
    """(figure id, CLIP score) of the k figures whose IMAGE is nearest to the question, best first.

    Stops with a clear message when no image embedding exists: a silent empty list would make the
    joint mode quietly equal to the text mode and spoil an evaluation run."""
    handbooks = list(handbooks) if handbooks is not None else None
    with connect(index.dsn) as conn:
        rows = conn.execute(IMAGE_RANK_SQL, {"q": image_query_vector, "k": k, "handbooks": handbooks,
                                             "model": IMAGE_MODEL_NAME}).fetchall()
    if not rows:
        raise RuntimeError("no image embedding in the database: run python ingestion/embed_images.py")
    return [(int(fid), float(score)) for fid, score in rows]


def figures_from_chunks(chunk_rows, index):
    """[(figure id, score)] from chunks, best first. chunk_rows = (handbook id, figure numbers, score).

    A figure takes the score of the BEST chunk that cites it. A mention that is not a stored figure
    of that handbook is ignored (it cannot be shown). Ties: smaller figure id first."""
    lookup = {(d["handbook_id"], d["figure_number"]): fid for fid, d in index.documents.items()}
    best = {}
    for handbook_id, mentions, score in chunk_rows:
        for number in mentions:
            fid = lookup.get((handbook_id, number))
            if fid is not None and score > best.get(fid, float("-inf")):
                best[fid] = score
    return sorted(best.items(), key=lambda item: (-item[1], item[0]))


def rank_chunks(index, query_vector, k, handbooks=None):
    """The figures cited by the k chunks nearest to the question: [(figure id, chunk score)]."""
    handbooks = list(handbooks) if handbooks is not None else None
    with connect(index.dsn) as conn:
        rows = conn.execute(CHUNK_RANK_SQL, {"q": query_vector, "k": k, "handbooks": handbooks}).fetchall()
    return figures_from_chunks(rows, index)


def text_scores(index, query_vector, ids):
    """{figure id: text similarity} for the given ids."""
    if not ids:
        return {}
    with connect(index.dsn) as conn:
        rows = conn.execute(TEXT_SCORE_SQL, {"q": query_vector, "ids": list(ids)}).fetchall()
    return {int(fid): float(score) for fid, score in rows}


def fuse_rrf(ranked_lists, k, rrf_k=RRF_K):
    """Reciprocal Rank Fusion of several rankings: [(figure id, fused score)], best first, k of them.

    Only the RANKS are used, never the scores, so a text cosine and a CLIP cosine (different scales)
    can be combined. A figure in both lists adds both terms. Ties: smaller figure id first."""
    fused = {}
    for ranked in ranked_lists:
        for position, (fid, _score) in enumerate(ranked, start=1):
            fused[fid] = fused.get(fid, 0.0) + 1.0 / (rrf_k + position)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))[:k]


def rank_query(index, query, query_vector, k, handbooks=None, mode=None):
    """The ranking used by retrieve() and by the evaluation, for the chosen mode.

    Returns (ranked, best_text_score): ranked = [(figure id, TEXT similarity)] in the order of the
    mode; best_text_score = the text similarity of the best TEXT match (for the threshold).
    query_vector is the bge vector of the question (the evaluation computes it once)."""
    mode = mode or retrieval_mode()
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if mode == "text":
        ranked = rank(index, query_vector, k, handbooks)
        return ranked, (ranked[0][1] if ranked else None)
    text_ranked = rank(index, query_vector, CANDIDATES, handbooks)
    best_text = text_ranked[0][1] if text_ranked else None
    if mode in ("image", "joint"):
        image_ranked = rank_image(index, embed_image_query(query), CANDIDATES if mode == "joint" else k,
                                  handbooks)
        order = (fuse_rrf([text_ranked, image_ranked], k) if mode == "joint" else image_ranked[:k])
    else:
        passage_ranked = rank_chunks(index, query_vector, CHUNK_CANDIDATES, handbooks)
        order = (fuse_rrf([text_ranked, passage_ranked], k) if mode == "hybrid" else passage_ranked[:k])
    known = dict(text_ranked)
    missing = [fid for fid, _ in order if fid not in known]
    known.update(text_scores(index, query_vector, missing))
    return [(fid, known[fid]) for fid, _ in order if fid in known], best_text


def retrieve(query, k=5, index=None, query_vector=None, handbooks=None, mode=None):
    """Top-k figures for a question, or {"results": [], "reason": "no_adequate_answer"}.

    When figures are returned, "confidence" is "high", or "low" when the best score is below
    LOW_CONFIDENCE_BELOW (FR-002: a low-confidence match is shown with a visible notice).

    handbooks: optional list of handbook ids to search in (default None = all handbooks). The
    threshold is applied to the best score inside that selection.

    index and query_vector can be passed in (tests do); by default they are loaded.
    mode: "text", "image", "joint", "passages" or "hybrid" (P7-30); None = RETRIEVAL_MODE. "score" is always the text
    similarity, and the threshold is applied to the best TEXT match in every mode.
    """
    index = index or load_index()
    if query_vector is None:
        query_vector = embed_query(query)
    ranked, best_text = rank_query(index, query, query_vector, k, handbooks, mode)
    if not ranked or best_text is None or best_text < THRESHOLD:
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
            # UC-07 "View source": stored image of the page, and the FAA PDF opened at that page
            "page_image_url": f"/figures/{i}/page-image" if d.get("page_image_path") else None,
            # NFR-001: compressed thumbnail first; image_url is the full-size image, loaded on request
            "thumbnail_url": f"/figures/{i}/thumbnail" if d.get("thumbnail_path") else None,
            "source_pdf_url": (f"{d['source_url']}#page={d['pdf_page']}"
                               if d.get("source_url") and d.get("pdf_page") else None),
        })
    confidence = "low" if best_text < LOW_CONFIDENCE_BELOW else "high"
    return {"results": results, "reason": None, "confidence": confidence}


def image_path_for(figure_id):
    """Image file of a figure by DATABASE id, or None if the id is not in the index.

    The printed number ("3-1") is not an id: it exists in every handbook. The path comes from the
    index, never from the text of the URL."""
    d = _figure(figure_id)
    return d["image_path"] if d and d["image_path"].is_file() else None


def page_image_path_for(figure_id):
    """Stored image of the page a figure is on (UC-07), by DATABASE id; None if unknown or not rendered."""
    d = _figure(figure_id)
    path = d.get("page_image_path") if d else None
    return path if path and path.is_file() else None


def thumbnail_path_for(figure_id):
    """Thumbnail of a figure (NFR-001), by DATABASE id; None if unknown or not made."""
    d = _figure(figure_id)
    path = d.get("thumbnail_path") if d else None
    return path if path and path.is_file() else None


def _figure(figure_id):
    """The index entry of a DATABASE id given as int or digit string, else None (never a path)."""
    if isinstance(figure_id, str) and figure_id.isascii() and figure_id.isdigit():
        figure_id = int(figure_id)
    if not isinstance(figure_id, int) or isinstance(figure_id, bool):
        return None
    return load_index().documents.get(figure_id)
