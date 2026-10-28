"""Inspect a handbook PDF BEFORE designing the extractor.

Usage (from the repository root):
    python ingestion/inspect_pdf.py data/raw/FAA-H-8083-15B.pdf

Why: the brief says FAA-H-8083-15B holds 2,287 embedded image objects. That is
NOT the number of figures: one figure can be made of several image objects,
some figures are vector drawings (no image object at all), and logos/icons are
image objects that are not figures. Captions ("Figure 3-12. ...") are the
reliable signal, so this script counts both and lets you compare them.

Output:
  - a summary printed to the terminal
  - data/inspect/<name>_pages.csv  : one row per PDF page
  - data/inspect/<name>_captions.csv : one row per detected caption
"""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf  # pip install pymupdf

# A caption is a text block that STARTS with "Figure 3-12." (strict) or
# "Figure 3-12" followed by something else (loose; may be prose like
# "Figure 3-12 shows...", so it is reported separately for manual checking).
CAPTION_STRICT = re.compile(r"^\s*Figure\s+(\d+-\d+)\.\s")
CAPTION_LOOSE = re.compile(r"^\s*Figure\s+(\d+-\d+)\b")
# Printed page numbers in FAA handbooks look like "3-12", in the page footer.
PRINTED_PAGE = re.compile(r"^\s*(\d{1,2}-\d{1,3})\s*$")
FOOTER_ZONE = 0.92  # bottom 8 % of the page


def printed_page_number(page):
    limit = page.rect.height * FOOTER_ZONE
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        if y0 >= limit:
            for line in text.splitlines():
                m = PRINTED_PAGE.match(line)
                if m:
                    return m.group(1)
    return ""


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python ingestion/inspect_pdf.py <path-to-pdf>")
    pdf_path = Path(sys.argv[1])
    out_dir = Path("data") / "inspect"
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    print(f"File      : {pdf_path}")
    print(f"Pages     : {doc.page_count}")
    for key in ("title", "author", "creationDate", "producer"):
        print(f"{key:10}: {doc.metadata.get(key)}")

    page_rows, caption_rows = [], []
    unique_images = set()
    captions_by_number = defaultdict(list)

    for page in doc:
        images = page.get_images(full=True)
        unique_images.update(img[0] for img in images)  # img[0] = xref (object id)
        drawings = len(page.get_drawings())             # vector paths on the page
        printed = printed_page_number(page)
        strict = loose = 0
        for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
            first_line = text.strip().splitlines()[0] if text.strip() else ""
            m_strict = CAPTION_STRICT.match(text)
            m_loose = CAPTION_LOOSE.match(text)
            if m_strict:
                strict += 1
            elif m_loose:
                loose += 1
            if m_loose:
                number = m_loose.group(1)
                captions_by_number[number].append(page.number + 1)
                caption_rows.append({
                    "figure": number,
                    "pdf_page": page.number + 1,          # 1-based position in the file
                    "printed_page": printed,              # number printed on the page
                    "kind": "strict" if m_strict else "loose",
                    "text": first_line[:150],
                })
        page_rows.append({
            "pdf_page": page.number + 1,
            "printed_page": printed,
            "text_chars": len(page.get_text()),
            "image_objects": len(images),
            "vector_drawings": drawings,
            "captions_strict": strict,
            "captions_loose": loose,
        })

    name = pdf_path.stem
    for rows, suffix in ((page_rows, "pages"), (caption_rows, "captions")):
        path = out_dir / f"{name}_{suffix}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
        print(f"Wrote     : {path}")

    total_refs = sum(r["image_objects"] for r in page_rows)
    strict_total = sum(1 for r in caption_rows if r["kind"] == "strict")
    pages_without_printed = sum(1 for r in page_rows if not r["printed_page"])
    duplicates = {k: v for k, v in captions_by_number.items() if len(v) > 1}

    # Gaps: if chapter 3 has Figure 3-1 .. 3-40 but 3-17 is missing, the caption
    # detector probably missed it (or the handbook skips it). Check by hand.
    gaps = []
    by_chapter = defaultdict(set)
    for number in captions_by_number:
        ch, n = number.split("-")
        by_chapter[int(ch)].add(int(n))
    for ch, nums in sorted(by_chapter.items()):
        missing = sorted(set(range(1, max(nums) + 1)) - nums)
        if missing:
            gaps.append(f"ch.{ch}: missing {missing[:10]}{' ...' if len(missing) > 10 else ''}")

    print("\n=== SUMMARY ===")
    print(f"Image objects placed on pages : {total_refs}")
    print(f"Unique image objects (xrefs)  : {len(unique_images)}")
    print(f"Pages with >=1 image object   : {sum(1 for r in page_rows if r['image_objects'])}")
    print(f"Captions (strict 'Figure X-Y.'): {strict_total}")
    print(f"Captions (loose, check by hand): {len(caption_rows) - strict_total}")
    print(f"Distinct figure numbers       : {len(captions_by_number)}")
    print(f"Chapters with figures         : {len(by_chapter)}")
    print(f"Figure numbers seen twice+    : {len(duplicates)} {list(duplicates)[:10]}")
    print(f"Pages with no printed number  : {pages_without_printed}")
    print("Numbering gaps                :", "; ".join(gaps) if gaps else "none")


if __name__ == "__main__":
    main()
