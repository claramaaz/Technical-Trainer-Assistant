"""FastAPI app: POST /login, POST /chat, POST/GET /admin/documents, GET /admin/ingestion-jobs/{id}, POST /flags, GET /admin/flags, POST /logout, GET /me, GET /admin/ping, GET /search, GET /answer, GET /figures/{id}/image, GET /figures/{id}/thumbnail,
GET /figures/{id}/page-image, GET /health,
and the React page at /
(the built files in frontend/dist; create them with: cd frontend && npm run build).

Run from the repository root:   python -m uvicorn backend.app:app
Login (P7-35, backend/auth.py): every route except /health, /login, /logout and the page itself
needs a logged-in user (401 otherwise); /admin/* also needs the Admin role (403 otherwise). Every question to /search and /answer is written to query_log (FR-007, backend/query_log.py).
At start-up, warm_up() loads the embedding model and the figure index, so the first learner after a
(re)start does not wait for them (NFR-001; the query log showed 30.6 s for the first question without it).
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend import auth, flags, ingest_jobs, retrieval
from backend.answer import generate_answer
from backend.chat import chat_turn
from backend.query_log import elapsed_ms, log_query
from backend.retrieval import image_path_for, page_image_path_for, retrieve, thumbnail_path_for

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
        if retrieval.retrieval_mode() != "text":
            retrieval.embed_image_query("warm-up")  # P7-30: the CLIP model too, in image/joint mode
    except Exception as exc:
        log.warning("warm-up failed (%s): %s", type(exc).__name__, exc)
        return False
    log.info("warm-up done in %d ms: model and index loaded", elapsed_ms(start))
    return True


def close_interrupted_jobs():
    """P7-54: an ingestion job cut by a restart can never finish; mark it failed so the admin sees it."""
    try:
        count = ingest_jobs.mark_interrupted()
    except Exception as exc:
        log.warning("could not check the ingestion jobs (%s): %s", type(exc).__name__, exc)
        return
    if count:
        log.warning("%d ingestion job(s) were interrupted by the restart and marked failed", count)


@asynccontextmanager
async def lifespan(app):
    warm_up()
    close_interrupted_jobs()
    yield


app = FastAPI(title="Technical Training Assistant", lifespan=lifespan)

# JS and CSS files of the build. Mounted only if the build exists, so the API still starts without it.
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/health")
def health():
    return {"status": "ok"}


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


@app.post("/login")
def login(body: LoginBody, response: Response):
    user = auth.authenticate(body.email, body.password)
    if user is None:
        # UC-05 A1: one generic message, so it does not say whether the email exists.
        raise HTTPException(status_code=401, detail="Wrong email or password")
    token = auth.make_token(user)
    response.set_cookie(auth.COOKIE_NAME, token, max_age=auth.TOKEN_MINUTES * 60, httponly=True,
                        samesite="strict", secure=auth.cookie_secure(), path="/")
    # The token is also returned for scripts and API clients (Authorization: Bearer).
    # The React page does not store it: it relies on the httpOnly cookie.
    return {"email": user["email"], "role": user["role"], "access_token": token, "token_type": "bearer"}


@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/", samesite="strict", secure=auth.cookie_secure(),
                           httponly=True)
    return {"status": "logged out"}


@app.get("/me")
def me(user=Depends(auth.current_user)):
    return {"email": user["email"], "role": user["role"]}


@app.get("/admin/ping")
def admin_ping(user=Depends(auth.require_admin)):
    # Placeholder admin route proving the server-side role check (BR-003) until the admin
    # screens exist (week 5+). A Learner gets 403 here.
    return {"status": "ok", "role": user["role"]}


class FlagBody(BaseModel):
    figure_id: int = Field(ge=1)                      # the database id of a returned figure
    query: str = Field(min_length=1, max_length=500)  # the question it was returned for
    reason: str | None = Field(default=None, max_length=500)


@app.post("/flags", status_code=201)
def flag_figure(body: FlagBody, response: Response, user=Depends(auth.current_user)):
    # UC-03: a Learner (or Admin) reports a returned figure as wrong; it goes to the QA queue.
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must not be blank")
    result = flags.save_flag(body.figure_id, user["id"], query, flags.clean_reason(body.reason))
    if result == flags.UNKNOWN_FIGURE:
        raise HTTPException(status_code=404, detail="figure not found")
    if result == flags.UNKNOWN_USER:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if result == flags.DUPLICATE:          # UC-03 A1: already reported, nothing new stored
        response.status_code = 200
        return {"status": "already_reported"}
    return {"status": "reported"}


@app.get("/admin/flags")
def admin_flags(user=Depends(auth.require_admin)):
    # The open reports for the QA queue page (FR-003). Admins only (403 for a Learner).
    return {"flags": flags.open_flags()}


@app.get("/search", dependencies=[Depends(auth.current_user)])
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


@app.get("/answer", dependencies=[Depends(auth.current_user)])
def answer(q: str = Query(..., min_length=1, max_length=500), k: int = Query(5, ge=1, le=20)):
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank")
    query, start = q.strip(), time.perf_counter()
    try:
        found = retrieve(query, k)
        answer_ = generate_answer(query, found["results"], found["reason"],
                                  confidence=found.get("confidence"))
        if answer_["mode"] == "no_answer" and found["results"]:
            # The LLM found no passage about the question on a low-confidence match (answer.py, rule 4).
            # FR-002 / UC-02 A1: show no weak match, and count the question as unanswered (FR-007).
            found = {"results": [], "reason": retrieval.NO_ANSWER}
    except Exception as exc:
        log_query("answer", query, elapsed_ms(start), error=exc)
        raise
    log_query("answer", query, elapsed_ms(start), found=found, answer_mode=answer_.get("mode"))
    body = {"answer": answer_, "results": found["results"]}
    if "confidence" in found:          # same rule as /search: only present when figures are returned
        body["confidence"] = found["confidence"]
    return body


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)  # earlier turns, oldest first
    k: int = Field(5, ge=1, le=20)


@app.post("/chat", dependencies=[Depends(auth.current_user)])
def chat(body: ChatBody):
    # P7-51 (supervisor, 13 Nov 2026): cumulative RAG chat. The browser sends the conversation so far
    # with every message, so follow-up questions work. See backend/chat.py for the 4 steps.
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="message must not be blank")
    start = time.perf_counter()
    try:
        turn = chat_turn(message, [m.model_dump() for m in body.history], body.k)
    except Exception as exc:
        log_query("chat", message, elapsed_ms(start), error=exc)
        raise
    found = {"results": turn["results"], "reason": turn["reason"]}
    if "confidence" in turn:
        found["confidence"] = turn["confidence"]
    log_query("chat", message, elapsed_ms(start), found=found, answer_mode=turn["answer"]["mode"],
              rewritten_query=turn["question"] if turn["question"] != message else None)
    return turn


@app.post("/admin/documents", status_code=202)
def upload_document(file: UploadFile = File(...), id: str = Form(...), title: str = Form(...),
                    source_url: str = Form(...), licence: str = Form(...), retrieved_at: str = Form(""),
                    user=Depends(auth.require_admin)):
    # P7-54 (UC-01, BR-001, BR-003; supervisor 13 Nov): an Admin uploads a handbook PDF from the
    # Sources panel. The file is checked and stored, then the ingestion runs in the background:
    # 202 Accepted with the job id; the page follows the job with GET /admin/ingestion-jobs/{id}.
    try:
        job_id = ingest_jobs.save_upload(file.file, id, title, source_url, licence, retrieved_at, user["id"])
    except ingest_jobs.UploadError as exc:
        raise HTTPException(status_code=exc.args[1], detail=exc.args[0]) from None
    ingest_jobs.start(job_id)
    return {"job_id": job_id, "status": "queued"}


@app.get("/admin/documents")
def admin_documents(user=Depends(auth.require_admin)):
    # The Sources panel (P7-40): every handbook in the database and the recent ingestion jobs.
    return {"documents": ingest_jobs.list_documents(), "jobs": ingest_jobs.list_jobs()}


@app.get("/admin/ingestion-jobs/{job_id}")
def admin_ingestion_job(job_id: int, user=Depends(auth.require_admin)):
    job = ingest_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.get("/figures/{figure_id}/image", dependencies=[Depends(auth.current_user)])
def figure_image(figure_id: str):
    # figure_id is the DATABASE id. The file path comes from the index, never from the URL.
    path = image_path_for(figure_id)
    if path is None:
        raise HTTPException(status_code=404, detail="figure not found")
    return FileResponse(path, media_type="image/png")


@app.get("/figures/{figure_id}/thumbnail", dependencies=[Depends(auth.current_user)])
def figure_thumbnail(figure_id: str):
    # NFR-001: the compressed thumbnail shown first. DATABASE id, path from the index.
    path = thumbnail_path_for(figure_id)
    if path is None:
        raise HTTPException(status_code=404, detail="thumbnail not available")
    return FileResponse(path, media_type="image/webp")


@app.get("/figures/{figure_id}/page-image", dependencies=[Depends(auth.current_user)])
def figure_page_image(figure_id: str):
    # UC-07: the stored image of the handbook page the figure is on. DATABASE id, path from the index.
    path = page_image_path_for(figure_id)
    if path is None:
        raise HTTPException(status_code=404, detail="page image not available")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/")
def page():
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend not built. Run: cd frontend && npm install && npm run build")
    return FileResponse(index, media_type="text/html")
