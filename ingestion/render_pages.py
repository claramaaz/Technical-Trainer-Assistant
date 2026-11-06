"""Render an image of every page of a handbook and record it in pages.image_path (P7-47; SPEC UC-07).

Usage (from the repository root, database running, handbook loaded):
    python ingestion/render_pages.py FAA-H-8083-15B
    python ingestion/render_pages.py FAA-H-8083-25C

Why: "View source" (UC-07) shows the returned figure next to an image of the original handbook
page, rendered and stored at ingestion, so the learner can check the figure and its page.

Reads data/raw/<handbook>.pdf, writes data/extracted/<handbook>/pages/p0001.jpg ... (JPEG, 100 dpi
by default: readable on a phone, about 100-200 KB a page). Resumable: pages that already have an
image file are skipped; every 20 pages are committed. data/ is not in Git.
"""
import argparse
import sys
from pathlib import Path

import fitz  # PyMuPDF
import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

DPI = 100
QUALITY = 75
COMMIT_EVERY = 20


def page_key(handbook_id, pdf_index):
    return f"{handbook_id}/pages/p{pdf_index:04d}.jpg"


def render_handbook(conn, handbook_id, root=ROOT, dpi=DPI):
    """Render the pages that have no image yet. Returns {"rendered": n, "skipped": n}."""
    root = Path(root)
    pdf_path = root / "data" / "raw" / f"{handbook_id}.pdf"
    if not pdf_path.is_file():
        raise FileNotFoundError(f"{pdf_path} not found (download it with ingestion/download_handbook.py)")
    pages = [i for (i,) in conn.execute(
        "SELECT pdf_index FROM pages WHERE document_id = %s ORDER BY pdf_index", (handbook_id,))]
    if not pages:
        raise ValueError(f"{handbook_id}: no pages in the database (load it first with ingestion/load_db.py)")
    out_root = root / "data" / "extracted"
    rendered = skipped = 0
    with fitz.open(pdf_path) as pdf:
        if pages[-1] > pdf.page_count:
            raise ValueError(f"{handbook_id}: the database has page {pages[-1]} but the PDF has {pdf.page_count}")
        for pdf_index in pages:
            key = page_key(handbook_id, pdf_index)
            path = out_root / key
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                pdf[pdf_index - 1].get_pixmap(dpi=dpi).save(path, jpg_quality=QUALITY)
                rendered += 1
            else:
                skipped += 1
            conn.execute("UPDATE pages SET image_path = %s WHERE document_id = %s AND pdf_index = %s",
                         (key, handbook_id, pdf_index))
            if (rendered + skipped) % COMMIT_EVERY == 0:
                conn.commit()
                print(f"  {rendered + skipped}/{len(pages)}", flush=True)
    conn.commit()
    return {"rendered": rendered, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("handbook_id")
    args = parser.parse_args()
    with psycopg.connect(connection_string()) as conn:
        result = render_handbook(conn, args.handbook_id)
        done, total = conn.execute("SELECT count(image_path), count(*) FROM pages WHERE document_id = %s",
                                   (args.handbook_id,)).fetchone()
    folder = ROOT / "data" / "extracted" / args.handbook_id / "pages"
    size_mb = sum(p.stat().st_size for p in folder.glob("*.jpg")) / 1e6
    print(f"{args.handbook_id}: {result['rendered']} rendered now, {result['skipped']} already there; "
          f"{done}/{total} pages have an image ({size_mb:.1f} MB in {folder})")


if __name__ == "__main__":
    main()
