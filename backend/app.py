"""FastAPI app: GET /search, GET /figures/{id}/image, GET /health, and the React page at /
(the built files in frontend/dist; create them with: cd frontend && npm run build).

Run from the repository root:   python -m uvicorn backend.app:app
No login yet.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.retrieval import image_path_for, retrieve

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

app = FastAPI(title="Technical Training Assistant")

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
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="Frontend not built. Run: cd frontend && npm install && npm run build")
    return FileResponse(index, media_type="text/html")
