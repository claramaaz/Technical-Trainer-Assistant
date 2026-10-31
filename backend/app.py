"""FastAPI app: GET /search, GET /figures/{id}/image, GET /health, and the page at /.

Run from the repository root:   python -m uvicorn backend.app:app
No login yet.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from backend.retrieval import image_path_for, retrieve

FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

app = FastAPI(title="Technical Training Assistant")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
def search(q: str = Query(..., min_length=1, max_length=500), k: int = Query(5, ge=1, le=20)):
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank")
    return retrieve(q.strip(), k)


@app.get("/figures/{figure_id}/image")
def figure_image(figure_id: str):
    # The file path comes from the index, never from the URL, so "../" tricks find nothing.
    path = image_path_for(figure_id)
    if path is None:
        raise HTTPException(status_code=404, detail="figure not found")
    return FileResponse(path, media_type="image/png")


@app.get("/")
def page():
    return FileResponse(FRONTEND, media_type="text/html")
