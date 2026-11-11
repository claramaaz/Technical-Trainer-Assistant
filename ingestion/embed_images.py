"""Compute the image embedding of every figure and store it in figure_image_embeddings (P7-30).

Usage (from the repository root, database running, migration 006 applied):
    python ingestion/embed_images.py            # only the figures that have no image embedding yet
    python ingestion/embed_images.py --all      # recompute every figure (e.g. after changing the model)

Why: brief section 4 asks for "joint retrieval over text and images". The text search (bge-small)
only sees the caption and the citing paragraph. This script gives every figure a second vector,
computed from the PICTURE itself, with CLIP ("clip-ViT-B-32" in sentence-transformers). CLIP puts
images and English sentences in the same 512-dimension space, so a question can be compared with an
image directly (backend/retrieval.py, rank_image()).

Input: the PNG files of data/extracted/<handbook>/figures/, found through figures.image_path.
Re-run after load_db.py reloads a handbook (the reload deletes the old image embeddings).
"""
import argparse
import sys
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

IMAGE_MODEL_NAME = "clip-ViT-B-32"   # the same name is used in backend/retrieval.py
BATCH = 32                            # images encoded together; small enough for a laptop CPU


def figures_to_embed(conn, redo_all=False):
    """(figure id, image key) of the figures to embed, in id order.

    Without redo_all: only figures with no image embedding, or one made by another model."""
    if redo_all:
        sql = "SELECT id, image_path FROM figures ORDER BY id"
        return conn.execute(sql).fetchall()
    sql = """SELECT f.id, f.image_path FROM figures f
             LEFT JOIN figure_image_embeddings e ON e.figure_id = f.id
             WHERE e.figure_id IS NULL OR e.model <> %s
             ORDER BY f.id"""
    return conn.execute(sql, (IMAGE_MODEL_NAME,)).fetchall()


def open_rgb(path):
    """The image as RGB (CLIP expects 3 channels; some PNGs are greyscale or have transparency)."""
    with Image.open(path) as img:
        return img.convert("RGB")


def save(conn, figure_ids, vectors):
    for fid, vec in zip(figure_ids, vectors):
        conn.execute(
            """INSERT INTO figure_image_embeddings (figure_id, model, embedding) VALUES (%s, %s, %s)
               ON CONFLICT (figure_id) DO UPDATE
               SET model = EXCLUDED.model, embedding = EXCLUDED.embedding, embedded_at = now()""",
            (fid, IMAGE_MODEL_NAME, vec))


def embed_images(conn, model, image_root=None, redo_all=False, batch=BATCH):
    """Returns {"embedded": n, "missing": [figure ids whose image file is missing]}.

    model: anything with encode(list of PIL images, normalize_embeddings=True) -> vectors.
    Tests pass a fake model; the real run passes CLIP. Commits after every batch, so an
    interrupted run keeps what was done and the next run continues from there."""
    image_root = Path(image_root or ROOT / "data" / "extracted")
    register_vector(conn)   # so a numpy vector can be written to a vector(512) column
    todo = figures_to_embed(conn, redo_all)
    missing, embedded = [], 0
    for start in range(0, len(todo), batch):
        ids, images = [], []
        for fid, key in todo[start:start + batch]:
            path = image_root / key
            if not path.is_file():
                missing.append(fid)
                continue
            ids.append(fid)
            images.append(open_rgb(path))
        if images:
            vectors = model.encode(images, normalize_embeddings=True)
            save(conn, ids, vectors)
            conn.commit()
            embedded += len(ids)
        print(f"  {min(start + batch, len(todo))}/{len(todo)} figures done", flush=True)
    return {"embedded": embedded, "missing": missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="recompute every figure")
    args = parser.parse_args()
    from sentence_transformers import SentenceTransformer
    print(f"Loading {IMAGE_MODEL_NAME} ...")
    model = SentenceTransformer(IMAGE_MODEL_NAME)
    with psycopg.connect(connection_string()) as conn:
        result = embed_images(conn, model, redo_all=args.all)
        total = conn.execute("SELECT count(*) FROM figure_image_embeddings WHERE model = %s",
                             (IMAGE_MODEL_NAME,)).fetchone()[0]
        figures = conn.execute("SELECT count(*) FROM figures").fetchone()[0]
    print(f"Embedded now: {result['embedded']}. Missing image files: {len(result['missing'])}"
          + (f" (figure ids {result['missing'][:20]})" if result["missing"] else ""))
    print(f"Figures with an image embedding ({IMAGE_MODEL_NAME}): {total} of {figures}")


if __name__ == "__main__":
    main()
