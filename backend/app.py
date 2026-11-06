"""FastAPI app: GET /search, GET /answer, GET /figures/{id}/image, GET /health, and the React page at /
(the built files in frontend/dist; create them with: cd frontend && npm run build).

Run from the repository root:   python -m uvicorn backend.app:app
No login yet. Every question to /search and /answer is written to query_log (FR-007, backend/query_log.py).
At start-up, warm_up() loads the embedding model and the figure index, so the first learner after a
(re)start does not wait for them (NFR-001; the query log showed 30.6 s for the first question without it).
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import retrieval
from backend.answer import generate_answer
from backend.query_log import elapsed_ms, log_query
from backend.retrieval import image_path_for, retrieve

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

log = logging.getLogger("uvicorn.error")  # shown in the uvicorn terminal


def warm_up():
    """Load the figure index and the embedding model once, before the first question.

    Returns True when both are ready. If the database is down, it only logs a warning and
    returns False: the server still starts (/health answers) and the first question loads them."""
    start = time.perf_counter()
    try:
        retrieval.load_index()          # cached (lru_cache): later calls reuse it
        retrieval.embed_query("warm-up")  # loads the model (cached) and runs one encoding
    except Exception as exc:
        log.warning("warm-up failed (%s): %s", type(exc).__name__, exc)
        return False
    log.info("warm-up done in %d ms: model and index loaded", elapsed_ms(start))
    return True


@asynccontextmanager
async def lifespan(app):
    warm_up()
    yield


app = FastAPI(title="Technical Training Assistant", lifespan=lifespan)

# JS and CSS files of the build. Mounted only if the build exists, so the API still starts without it.
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(q: str = Query(..., min_length=1, max_length=500), k: int = Query(5, ge=1, le=20)):
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank")
    query, start = q.strip(), time.perf_counter()
    try:
        found = retrieve(query, k)
    except Exception as exc:
        log_query("search", query, elapsed_ms(start), error=exc)
        raise
    log_query("search", query, elapsed_ms(start), found=found)
    return found


@app.get("/answer")
def answer(q: str = Query(..., min_length=1, max_length=500), k: int = Query(5, ge=1, le=20)):
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank")
    query, start = q.strip(), time.perf_counter()
    try:
        found = retrieve(query, k)
        answer_ = generate_answer(query, found["results"], found["reason"])
    except Exception as exc:
        log_query("answer", query, elapsed_ms(start), error=exc)
        raise
    log_query("answer", query, elapsed_ms(start), found=found, answer_mode=answer_.get("mode"))
    return {"answer": answer_, "results": found["results"]}


@app.get("/figures/{figure_id}/image")
def figure_image(figure_id: str):
    # figure_id is the DATABASE id. The file path comes from the index, never from the URL.
    path = image_path_for(figure_id)
    if path is None:
        raise HTTPException(status_code=404, detail="figure not found")
    return FileResponse(path, media_type="image/png")


@app.get("/")
def page():
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend not built. Run: cd frontend && npm install && npm run build")
    return FileResponse(index, media_type="text/html")
