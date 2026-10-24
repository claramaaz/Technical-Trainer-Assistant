"""Extract figures, captions, page provenance and referencing paragraphs.

Usage (from the repository root):
    python ingestion/extract_figures.py data/raw/FAA-H-8083-15B.pdf

Method (caption-first, see SPEC 5.1):
 1. On each page, collect "graphic boxes": the rectangles of embedded images
    AND of vector drawings. Vector drawings matter: many FAA diagrams contain
    no image object at all, so counting images alone would miss them.
 2. Merge boxes that touch or nearly touch into one "region". One figure is
    often made of several pieces (an image plus arrows plus a frame).
 3. Find captions: text blocks starting with "Figure 3-12." (strict form).
 4. Bind each caption to the closest unused region ABOVE it that overlaps it
    horizontally (FAA handbooks print captions under the figure). Sideways
    captions on landscape pages bind to the region on their LEFT. Vector
    paths are cut to their clipping area first, and pieces separated by a
    caption are never merged (fixes found on the real FAA-H-8083-15B).
 5. Render each bound region as a PNG with page.get_pixmap(clip=region). The
    PNG therefore shows exactly what a reader sees, labels included.
 6. Regions with no caption are saved as UNBOUND (for the admin QA queue).
    Captions with no region are saved as caption_only (also for QA).
 7. Second pass: every text block that mentions "Figure 3-12" (and is not
    the caption itself) is stored as a referencing paragraph.

Outputs, in data/extracted/<handbook-id>/:
    figures/<figure-number>.png   one image per bound figure
    unbound/p<page>_<n>.png       regions without a caption
    figures.jsonl                 one JSON object per line (bound + caption_only)
    unbound.jsonl                 one JSON object per unbound region
    report.json                   the counts for the Week 1 gate
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_pdf import printed_page_number  # same footer rule as the inspector

CAPTION = re.compile(r"^\s*Figure\s+(\d+-\d+)\.\s")       # caption block
MENTION = re.compile(r"\bFigures?\s+(\d+-\d+)")           # "see Figure 3-12"
MENTION_RANGE = re.compile(r"\bFigures?\s+(\d+)-(\d+)\s+(?:through|to|and)\s+(\d+)-(\d+)")

# Tunable thresholds, in PDF points (72 points = 1 inch). Kept here so they
# are easy to find, change and report in EVALUATION.md.
HEADER_ZONE = 0.06     # ignore graphics in the top 6 % of the page (header rule)
FOOTER_ZONE = 0.92     # ...and in the bottom 8 % (footer rule, page number)
MERGE_GAP = 12         # boxes closer than this are the same figure
MIN_SIDE = 40          # a region smaller than 40 pt on either side is decoration
MAX_PAGE_SHARE = 0.95  # a box covering ~the whole page is a background
MAX_CAPTION_GAP = 120  # a caption farther than this below a region is not its caption
RENDER_DPI = 150       # good enough on a phone, small files
PAD = 6                # margin added around a region when rendering it
LONG_PARAGRAPH = 250   # characters; a text block this long inside a crop = body text


def graphic_boxes(page):
    """Rectangles of images and vector drawings, minus headers/footers/backgrounds."""
    W, H = page.rect.width, page.rect.height
    boxes = [pymupdf.Rect(info["bbox"]) for info in page.get_image_info()]
    boxes += visible_drawing_rects(page)
    kept = []
    for b in boxes:
        b = b & page.rect                      # clip to the page
        if b.is_empty:
            continue
        if b.width * b.height > MAX_PAGE_SHARE * W * H:
            continue                           # page background
        if b.y1 < H * HEADER_ZONE or b.y0 > H * FOOTER_ZONE:
            continue                           # header / footer decoration
        kept.append(b)
    return kept


def visible_drawing_rects(page):
    """Rectangles of vector drawings, cut down to their clipping area.

    PDF artwork is often drawn larger than what is shown and then clipped
    (e.g. a line running off the page, PDF page 39). Without applying the clip,
    such a path pulls body text and footer into the figure region.
    In extended mode PyMuPDF lists "clip" entries with a nesting level; a path
    is limited by every clip of a lower level that is still open.
    """
    clips = {}                                 # level -> clip rectangle
    rects = []
    for d in page.get_drawings(extended=True):
        level = d["level"]
        if d["type"] == "clip":
            clips = {lv: r for lv, r in clips.items() if lv < level}
            clips[level] = pymupdf.Rect(d["scissor"])
        elif d["type"] in ("f", "s", "fs"):
            r = pymupdf.Rect(d["rect"])
            for lv, c in clips.items():
                if lv < level:
                    r &= c
            if not r.is_empty:
                rects.append(r)
    return rects


def merge_boxes(boxes, separators=()):
    """Union boxes that overlap or are within MERGE_GAP of each other.

    separators: caption rectangles. Two pieces are NOT merged when a caption
    lies between them, because a caption marks the end of one figure. Without
    this, two figures printed close together (e.g. Figures 3-5 and 3-6 on PDF
    page 72) became one region.
    """
    def grow(r):
        return pymupdf.Rect(r.x0 - MERGE_GAP, r.y0 - MERGE_GAP, r.x1 + MERGE_GAP, r.y1 + MERGE_GAP)

    def blocked(a, b):
        union = a | b
        return any(s.intersects(union) and not s.intersects(a) and not s.intersects(b)
                   for s in separators)

    regions = [pymupdf.Rect(b) for b in boxes]
    changed = True
    while changed:
        changed = False
        out = []
        while regions:
            r = regions.pop()
            i = 0
            while i < len(regions):
                if grow(r).intersects(regions[i]) and not blocked(r, regions[i]):
                    r |= regions.pop(i)
                    changed = True
                    i = 0                      # r grew: re-check the remaining boxes
                else:
                    i += 1
            out.append(r)
        regions = out
    return [r for r in regions if r.width >= MIN_SIDE and r.height >= MIN_SIDE]


def text_blocks(page):
    """(rect, text) for every text block, with line breaks joined into spaces."""
    return [(pymupdf.Rect(b[:4]), " ".join(b[4].split()))
            for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]


def is_vertical(rect):
    """A caption printed sideways (landscape chart pages): tall and narrow."""
    return rect.height > 3 * rect.width


def join_sideways_figure(captions, regions):
    """On a page with exactly one sideways caption, the whole landscape figure
    is everything to the LEFT of that caption (often several charts). Replace
    those regions by their union so they become one figure."""
    vertical = [c for c, _ in captions if is_vertical(c)]
    if len(vertical) != 1:
        return regions
    cap = vertical[0]
    left = [r for r in regions if r.x1 <= cap.x0 + MERGE_GAP and cap.x0 - r.x1 <= MAX_CAPTION_GAP]
    if len(left) < 2:
        return regions
    union = pymupdf.Rect(left[0])
    for r in left[1:]:
        union |= r
    return [r for r in regions if r not in left] + [union]


def bind(captions, regions):
    """Pair each caption with the nearest free region "above" it.

    For a normal caption "above" means higher on the page. For a sideways
    caption the page is read rotated, so "above" means to the LEFT.
    Returns dict caption_idx -> region_idx.
    """
    candidates = []
    for ci, (crect, _) in enumerate(captions):
        for ri, r in enumerate(regions):
            inside = crect & r
            if not inside.is_empty and inside.height > 0.5 * crect.height and \
                    crect.y0 > r.y0 + 0.6 * r.height and not is_vertical(crect):
                # Caption printed over the bottom part of the artwork (inside a
                # frame, or a line runs down beside it, e.g. Figure 7-41): match.
                candidates.append((0, ci, ri))
                continue
            if is_vertical(crect):
                gap = crect.x0 - r.x1          # >0 when the region is left of the caption
                overlap = min(crect.y1, r.y1) - max(crect.y0, r.y0)
            else:
                gap = crect.y0 - r.y1          # >0 when the region is above the caption
                overlap = min(crect.x1, r.x1) - max(crect.x0, r.x0)
            if -MERGE_GAP <= gap <= MAX_CAPTION_GAP and overlap > 0:
                candidates.append((gap, ci, ri))
    pairs, used_c, used_r = {}, set(), set()
    for gap, ci, ri in sorted(candidates):     # closest pairs first
        if ci not in used_c and ri not in used_r:
            pairs[ci] = ri
            used_c.add(ci)
            used_r.add(ri)
    return pairs


def expand_mentions(text):
    """Figure numbers mentioned in a paragraph, including 'Figures 3-4 through 3-6'."""
    found = set(MENTION.findall(text))
    for c1, n1, c2, n2 in MENTION_RANGE.findall(text):
        if c1 == c2 and int(n1) < int(n2) <= int(n1) + 30:
            found.update(f"{c1}-{n}" for n in range(int(n1), int(n2) + 1))
    return found


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python ingestion/extract_figures.py <path-to-pdf>")
    pdf_path = Path(sys.argv[1])
    handbook_id = pdf_path.stem
    out = Path("data") / "extracted" / handbook_id
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "unbound").mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    figures, unbound = [], []
    mentions = defaultdict(list)               # figure number -> referencing paragraphs
    seen_numbers = set()

    for page in doc:
        pdf_page = page.number + 1             # 1-based position in the file
        printed = printed_page_number(page)    # e.g. "3-12", cited to learners
        blocks = text_blocks(page)
        captions = [(r, t) for r, t in blocks if CAPTION.match(t)]
        regions = merge_boxes(graphic_boxes(page), separators=[r for r, _ in captions])
        regions = join_sideways_figure(captions, regions)
        pairs = bind(captions, regions)

        for ci, (crect, ctext) in enumerate(captions):
            number = CAPTION.match(ctext).group(1)
            record = {
                "handbook_id": handbook_id,
                "figure_number": number,
                "caption": ctext,
                "pdf_page": pdf_page,
                "printed_page": printed,
                "caption_bbox": [round(v, 1) for v in crect],
            }
            if number in seen_numbers:
                record["warning"] = "duplicate figure number (continued figure?)"
            seen_numbers.add(number)
            if ci in pairs:
                region = regions[pairs[ci]]
                png = out / "figures" / f"{number}.png"
                if png.exists():               # duplicate number: keep both files
                    png = out / "figures" / f"{number}_p{pdf_page}.png"
                page.get_pixmap(clip=(region + (-PAD, -PAD, PAD, PAD)) & page.rect, dpi=RENDER_DPI).save(png)
                record.update(status="bound", bbox=[round(v, 1) for v in region],
                              image_path=str(png.relative_to(out)).replace("\\", "/"))
                # A crop that contains a full body paragraph probably took in
                # surrounding text: send it to the admin QA queue.
                if any(r in region and len(t) > LONG_PARAGRAPH and not CAPTION.match(t)
                       for r, t in blocks):
                    record["needs_review"] = "crop contains a body paragraph"
            else:
                record.update(status="caption_only", bbox=None, image_path=None)
            figures.append(record)

        bound_regions = set(pairs.values())
        for ri, region in enumerate(regions):
            if ri in bound_regions:
                continue
            png = out / "unbound" / f"p{pdf_page}_{ri}.png"
            page.get_pixmap(clip=(region + (-PAD, -PAD, PAD, PAD)) & page.rect, dpi=RENDER_DPI).save(png)
            unbound.append({
                "handbook_id": handbook_id, "pdf_page": pdf_page, "printed_page": printed,
                "bbox": [round(v, 1) for v in region],
                "image_path": str(png.relative_to(out)).replace("\\", "/"),
            })

        for rect, text in blocks:
            if CAPTION.match(text):
                continue                       # the caption is not a referencing paragraph
            for number in expand_mentions(text):
                mentions[number].append({"pdf_page": pdf_page, "printed_page": printed,
                                         "text": text[:600]})

    for f in figures:
        f["referencing_paragraphs"] = mentions.get(f["figure_number"], [])

    with open(out / "figures.jsonl", "w", encoding="utf-8") as fh:
        for f in figures:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with open(out / "unbound.jsonl", "w", encoding="utf-8") as fh:
        for u in unbound:
            fh.write(json.dumps(u, ensure_ascii=False) + "\n")

    bound = [f for f in figures if f["status"] == "bound"]
    report = {
        "handbook_id": handbook_id,
        "pdf_pages": doc.page_count,
        "captions_found": len(figures),
        "figures_bound_to_caption": len(bound),
        "captions_without_region": len(figures) - len(bound),
        "unbound_regions": len(unbound),
        "figures_with_referencing_paragraph": sum(1 for f in figures if f["referencing_paragraphs"]),
        "figures_missing_printed_page": sum(1 for f in figures if not f["printed_page"]),
        "duplicate_figure_numbers": sum(1 for f in figures if "warning" in f),
        "bound_figures_flagged_for_review": sum(1 for f in figures if "needs_review" in f),
        "thresholds": {"MERGE_GAP": MERGE_GAP, "MIN_SIDE": MIN_SIDE,
                       "MAX_CAPTION_GAP": MAX_CAPTION_GAP, "RENDER_DPI": RENDER_DPI, "PAD": PAD,
                       "LONG_PARAGRAPH": LONG_PARAGRAPH},
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== EXTRACTION REPORT ===")
    for k, v in report.items():
        if k != "thresholds":
            print(f"{k:38}: {v}")
    print(f"Output folder                         : {out}")


if __name__ == "__main__":
    main()
