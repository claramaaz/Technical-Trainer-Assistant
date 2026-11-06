"""Make a small compressed thumbnail of every figure and record it in figures.thumbnail_path (P7-49).

Usage (from the repository root, database running, handbook loaded):
    python ingestion/make_thumbnails.py FAA-H-8083-15B
    python ingestion/make_thumbnails.py FAA-H-8083-25C

Why: NFR-001 (SPEC): "Figures are first shown as compressed thumbnails; the full-size image
loads on request", so the first results page loads in under 5 s on a 3G connection. The full
PNGs average about 200 KB; a learner on a phone first gets the thumbnail.

Thumbnail: at most 480 px wide or high (a phone screen), WebP, quality 70, written to
data/extracted/<handbook>/thumbnails/<figure>.webp. Resumable: an existing file is not made
again. Re-run after load_db.py reloads a handbook (the loader does not fill thumbnail_path).
"""
import argparse
import sys
from pathlib import Path

import psycopg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

MAX_SIDE = 480
QUALITY = 70


def thumbnail_key(handbook_id, image_key):
    """FAA-H-8083-15B/thumbnails/4-12.webp from FAA-H-8083-15B/figures/4-12.png."""
    return f"{handbook_id}/thumbnails/{Path(image_key).stem}.webp"


def make_thumbnails(conn, handbook_id, image_root=None):
    """Returns {"made": n, "skipped": n, "missing": [figure ids whose image file is missing]}."""
    image_root = Path(image_root or ROOT / "data" / "extracted")
    rows = conn.execute("SELECT id, image_path FROM figures WHERE document_id = %s ORDER BY id",
                        (handbook_id,)).fetchall()
    if not rows:
        raise ValueError(f"{handbook_id}: no figures in the database (load it first with ingestion/load_db.py)")
    made = skipped = 0
    missing = []
    for figure_id, image_key in rows:
        source = image_root / image_key
        key = thumbnail_key(handbook_id, image_key)
        target = image_root / key
        if target.is_file():
            skipped += 1
        elif not source.is_file():
            missing.append(figure_id)
            continue
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source) as im:
                im = im.convert("RGB")
                im.thumbnail((MAX_SIDE, MAX_SIDE))   # keeps the proportions, never enlarges
                im.save(target, "WEBP", quality=QUALITY)
            made += 1
        conn.execute("UPDATE figures SET thumbnail_path = %s WHERE id = %s", (key, figure_id))
    conn.commit()
    return {"made": made, "skipped": skipped, "missing": missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("handbook_id")
    args = parser.parse_args()
    with psycopg.connect(connection_string()) as conn:
        result = make_thumbnails(conn, args.handbook_id)
        done, total = conn.execute("SELECT count(thumbnail_path), count(*) FROM figures WHERE document_id = %s",
                                   (args.handbook_id,)).fetchone()
    folder = ROOT / "data" / "extracted" / args.handbook_id
    thumbs = sum(p.stat().st_size for p in (folder / "thumbnails").glob("*.webp")) / 1e6
    full = sum(p.stat().st_size for p in (folder / "figures").glob("*.png")) / 1e6
    print(f"{args.handbook_id}: {result['made']} made now, {result['skipped']} already there; "
          f"{done}/{total} figures have a thumbnail; {thumbs:.1f} MB of thumbnails vs {full:.1f} MB of "
          f"full images; missing image files: {result['missing'] or 'none'}")


if __name__ == "__main__":
    main()
