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
    Every image and drawing box is shrunk to where it leaves visible ink on
    a text-free render of the page, because images are often placed larger
    than what is shown.
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

import numpy as np
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
MERGE_GAP = 8          # boxes closer than this are the same figure (must stay below the ~11 pt column gutter)
MIN_SIDE = 40          # a region smaller than 40 pt on either side is decoration
MAX_PAGE_SHARE = 0.95  # a box covering ~the whole page is a background
MAX_CAPTION_GAP = 120  # a caption farther than this below a region is not its caption
RENDER_DPI = 150       # good enough on a phone, small files
PAD = 6                # margin added around a region when rendering it
LONG_PARAGRAPH = 250   # characters; a text block this long inside a crop = body text
INK_DPI = 50           # resolution of the text-free render used to find visible artwork
INK_LEVEL = 245        # a pixel darker than this (0-255) in any colour counts as ink
NEIGHBOUR_GAP = 40     # an uncaptioned piece this close beside a figure belongs to it
LABEL_GAP = 20         # a short text label this close to a figure belongs to it
LABEL_MAX_CHARS = 40   # longer text blocks are prose, not labels
LABEL_MAX_SIZE = 9.5   # figure labels use a small font (8-9 pt); body text is 10-11 pt, headings 12
SUSPECT_WEIGHT = 1000  # a suspect image counts as this many times larger when pieces compete for ink


def ink_map(gfx_page):
    """Render the page with all text removed and return a True/False grid:
    True where artwork (images or drawings) actually leaves visible ink.

    gfx_page is the same page in a second copy of the PDF; the text is
    removed there so the original stays untouched."""
    gfx_page.add_redact_annot(gfx_page.rect)
    gfx_page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                              text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    pix = gfx_page.get_pixmap(dpi=INK_DPI, colorspace=pymupdf.csRGB, alpha=False)
    pixels = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return pixels.min(axis=2) < INK_LEVEL


def pixel_box(box, shape):
    """Page-point rectangle -> (x0, y0, x1, y1) pixel slice bounds on the ink map."""
    k = INK_DPI / 72                           # page points -> pixels
    return (max(int(box.x0 * k), 0), max(int(box.y0 * k), 0),
            min(int(box.x1 * k) + 1, shape[1]), min(int(box.y1 * k) + 1, shape[0]))


def shrink_to_ink(box, ink, smallest=None, own_area=None):
    """Shrink a box to the part where ink is really visible. Returns None if
    nothing is visible inside it (fully clipped or white-on-white).

    Why: PDFs often place an image larger than what is shown (part of it
    off the page or hidden by a clip, e.g. Figure 9-19 on PDF page 263).
    The image's own rectangle then covers body text, and the crop does too.

    smallest: for every pixel, the area of the smallest piece covering it.
    A pixel's ink belongs to the smallest piece over it, so an oversized image
    cannot take ink from the real pictures it reaches over (PDF pages 138,
    195), and a real picture keeps its ink even when a huge invisible image
    covers it too (the sky strip of Figure 7-47)."""
    k = INK_DPI / 72
    x0, y0, x1, y1 = pixel_box(box, ink.shape)
    if x1 <= x0 or y1 <= y0:
        return None
    window = ink[y0:y1, x0:x1]
    if smallest is not None:
        window = window & (smallest[y0:y1, x0:x1] >= own_area * 0.98)
    rows = np.flatnonzero(window.any(axis=1))
    cols = np.flatnonzero(window.any(axis=0))
    if rows.size == 0:
        return None
    return pymupdf.Rect((x0 + cols[0]) / k, (y0 + rows[0]) / k,
                        (x0 + cols[-1] + 1) / k, (y0 + rows[-1] + 1) / k) & box


def smallest_area(pieces, sizes, shape):
    """For every ink-map pixel: the size of the smallest piece covering it
    (infinity where no piece does). sizes = each piece's area, multiplied by
    SUSPECT_WEIGHT for suspect images so that they lose every contest."""
    out = np.full(shape, np.inf)
    for b, size in sorted(zip(pieces, sizes), key=lambda bs: -bs[1]):   # big first, small overwrite
        x0, y0, x1, y1 = pixel_box(b, shape)
        if x1 > x0 and y1 > y0:
            out[y0:y1, x0:x1] = size
    return out


def graphic_boxes(page, ink=None):
    """Rectangles of images and vector drawings, minus headers/footers/backgrounds.
    With an ink map, each rectangle is first shrunk to its visible part."""
    W, H = page.rect.width, page.rect.height
    raw = [pymupdf.Rect(info["bbox"]) for info in page.get_image_info()]
    raw = [r for r in raw if not (r & page.rect).is_empty]
    images = [r & page.rect for r in raw]
    drawings = [d & page.rect for d in visible_drawing_rects(page)]
    drawings = [d for d in drawings if not d.is_empty]
    pieces = images + drawings
    # An image placed partly off the page, or reaching across both text
    # columns, is "suspect": it is probably larger than what is shown, so it
    # only gets ink that no ordinary piece claims (PDF pages 138 and 195).
    suspect = [not (r in page.rect + (-1, -1, 1, 1)) or
               (r.x0 < W * 0.45 and r.x1 > W * 0.55) for r in raw] + [False] * len(drawings)
    sizes = [max(b.get_area(), 1.0) * (SUSPECT_WEIGHT if sus else 1.0)
             for b, sus in zip(pieces, suspect)]
    smallest = smallest_area(pieces, sizes, ink.shape) if ink is not None and images else None
    kept = []
    for n, b in enumerate(pieces):
        if ink is not None:
            if n < len(images) and smallest is not None:
                # An image may be placed far larger than what is shown: it
                # only keeps the ink where it is the smallest piece.
                b = shrink_to_ink(b, ink, smallest, sizes[n])
            else:
                b = shrink_to_ink(b, ink)
            if b is None or b.is_empty:
                continue                       # nothing visible
        if b.width * b.height > MAX_PAGE_SHARE * W * H:
            continue                           # page background
        if b.y1 < H * HEADER_ZONE or b.y0 > H * FOOTER_ZONE:
            continue                           # header / footer decoration
        kept.append(b)
    return kept


def split_at_captions(boxes, captions, ink):
    """A single box that runs across a caption (part above, part below) covers
    two figures, e.g. an oversized image on PDF page 336 (Figure 11-13). Cut it
    at the caption and shrink each half to its visible ink again."""
    out = []
    for b in boxes:
        cut = None
        for c in captions:
            across = min(b.x1, c.x1) - max(b.x0, c.x0) > 0
            if across and b.y0 < c.y0 - MIN_SIDE / 2 and b.y1 > c.y1 + MIN_SIDE / 2:
                cut = c
                break
        if cut is None:
            out.append(b)
            continue
        for half in (pymupdf.Rect(b.x0, b.y0, b.x1, cut.y0), pymupdf.Rect(b.x0, cut.y1, b.x1, b.y1)):
            half = shrink_to_ink(half, ink) if ink is not None else half
            if half is not None and not half.is_empty:
                out.append(half)
    return out


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


def drop_contained(boxes):
    """Remove boxes lying entirely inside another box: they cannot change the
    outline of a merged region, and chart pages have thousands of them, which
    made merging slow (about 20 s per page)."""
    if len(boxes) < 2:
        return boxes
    a = np.array([[b.x0, b.y0, b.x1, b.y1] for b in boxes])
    keep = []
    for i in range(len(a)):
        inside = (a[:, 0] <= a[i, 0]) & (a[:, 1] <= a[i, 1]) & (a[:, 2] >= a[i, 2]) & (a[:, 3] >= a[i, 3])
        inside[i] = False
        same = inside & (a[:, 0] == a[i, 0]) & (a[:, 1] == a[i, 1]) & (a[:, 2] == a[i, 2]) & (a[:, 3] == a[i, 3])
        # drop if inside a different box, or an identical box that comes earlier
        if (inside & ~same).any() or same[:i].any():
            continue
        keep.append(boxes[i])
    return keep


def merge_boxes(boxes, separators=()):
    """Union boxes that overlap or are within MERGE_GAP of each other.

    separators: caption rectangles. Two pieces are NOT merged when a caption
    lies between them, because a caption marks the end of one figure. Without
    this, two figures printed close together (e.g. Figures 3-5 and 3-6 on PDF
    page 72) became one region.
    """
    def grow(r):
        return pymupdf.Rect(r.x0 - MERGE_GAP, r.y0 - MERGE_GAP, r.x1 + MERGE_GAP, r.y1 + MERGE_GAP)

    def own_caption(piece):
        """Index of the caption printed right below this piece, if any."""
        best = None
        for i, s in enumerate(separators):
            if is_vertical(s):
                continue
            gap = s.y0 - piece.y1
            overlap = min(s.x1, piece.x1) - max(s.x0, piece.x0)
            # a real overlap, not a 5 pt sliver at a column edge (7-1 / 7-3, PDF page 163)
            if 0 <= gap <= MERGE_GAP * 2 and overlap > 0.3 * min(s.width, piece.width):
                if best is None or gap < best[0]:
                    best = (gap, i)
        return None if best is None else best[1]

    # Two captions side by side mean two figures side by side: the line halfway
    # between them is a boundary that no merge may cross above them (7-1 / 7-3
    # on PDF page 163, joined by a strip image reaching 3 pt over the gap).
    flat = [c for c in separators if not is_vertical(c)]
    splits = []
    for c1 in flat:
        for c2 in flat:
            if c1.x1 <= c2.x0 and min(c1.y1, c2.y1) - max(c1.y0, c2.y0) > 0:
                splits.append(((c1.x1 + c2.x0) / 2, max(c1.y1, c2.y1)))

    # A piece that reaches over such a boundary is cut back to its own side
    # (the strip on PDF page 163 left a 3 pt sliver of 7-3 on the edge of 7-1).
    cut = []
    for b in boxes:
        b = pymupdf.Rect(b)
        for x, y_end in splits:
            if b.y0 < y_end and b.x0 < x < b.x1:
                if (b.x0 + b.x1) / 2 < x:
                    b.x1 = x
                else:
                    b.x0 = x
        cut.append(b)
    boxes = cut

    def across_split(a, b):
        for x, y_end in splits:
            ca_x, cb_x = (a.x0 + a.x1) / 2, (b.x0 + b.x1) / 2
            if (ca_x - x) * (cb_x - x) < 0 and a.y0 < y_end and b.y0 < y_end:
                return True
        return False

    def blocked(a, b):
        union = a | b
        if across_split(a, b):
            return True
        ca, cb = own_caption(a), own_caption(b)
        if ca is not None and cb is not None and ca != cb:
            return True                        # side by side, each with its own caption (5-37/5-38)
        for s in separators:
            centre = (s.tl + s.br) / 2
            if s.intersects(union) and not s.intersects(a) and not s.intersects(b):
                return True                    # caption lies between the two pieces
            if centre in union and centre not in a and centre not in b:
                return True                    # caption sits in the gap of a side-by-side pair
        return False

    regions = drop_contained([pymupdf.Rect(b) for b in boxes])
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
    regions = drop_contained(regions)          # a copy left inside a merged region
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
            if not inside.is_empty and not is_vertical(crect) and \
                    inside.height > 0.5 * crect.height and crect.y0 > r.y0 + 0.6 * r.height:
                # Caption printed over the bottom part of the artwork (inside a
                # frame, or a line runs down beside it, e.g. Figure 7-41): match.
                candidates.append((0, ci, ri))
                continue
            if not inside.is_empty and is_vertical(crect) and \
                    inside.width > 0.5 * crect.width and crect.x0 > r.x0 + 0.6 * r.width:
                # Sideways caption printed inside the right part of a framed chart.
                candidates.append((0, ci, ri))
                continue
            if is_vertical(crect):
                gap = crect.x0 - r.x1          # >0 when the region is left of the caption
                overlap = min(crect.y1, r.y1) - max(crect.y0, r.y0)
                need = 0.3 * min(crect.height, r.height)
            else:
                gap = crect.y0 - r.y1          # >0 when the region is above the caption
                overlap = min(crect.x1, r.x1) - max(crect.x0, r.x0)
                need = 0.3 * min(crect.width, r.width)
            # a real overlap, not a 2 pt sliver (7-3's caption under 7-1's figure, PDF page 163)
            if -MERGE_GAP <= gap <= MAX_CAPTION_GAP and overlap > need:
                candidates.append((gap, ci, ri))
    pairs, used_c, used_r = {}, set(), set()
    for gap, ci, ri in sorted(candidates):     # closest pairs first
        if ci not in used_c and ri not in used_r:
            pairs[ci] = ri
            used_c.add(ci)
            used_r.add(ri)
    return pairs


def no_caption_inside(rect, captions, allowed=None):
    """True if no caption centre (other than `allowed`) lies inside rect."""
    for c in captions:
        if c is allowed:
            continue
        if (c.tl + c.br) / 2 in rect:
            return False
    return True


def trim_caption(region, caption, ink):
    """If the caption is printed inside the figure's box, cut the box so the
    caption is not part of the image (Figures 1-18, 1-19: sideways caption
    inside a chart frame; 10-1, 5-37: caption inside the bottom of the box)."""
    if not region.intersects(caption):
        return region
    r = pymupdf.Rect(region)
    if is_vertical(caption):
        if caption.x0 > r.x0 + MIN_SIDE:
            r.x1 = min(r.x1, caption.x0 - 1)
    elif caption.y0 > r.y0 + MIN_SIDE:
        r.y1 = min(r.y1, caption.y0 - 1)
    # Only cut: re-shrinking to the ink map here would drop the text labels
    # (the ink map has no text), e.g. the axis titles of Figure 4-11.
    return r if not r.is_empty else region


def absorb_neighbours(region, others, captions, own_caption):
    """Add uncaptioned pieces lying right beside the figure, at the same
    height or just above/below, when no other caption is in between
    (Figure 6-20: two small instruments printed left and right of the chart).
    Returns the grown region and the indexes of the pieces it took."""
    taken = set()
    grown = True
    while grown:
        grown = False
        for i, u in enumerate(others):
            if i in taken:
                continue
            v_overlap = min(region.y1, u.y1) - max(region.y0, u.y0)
            h_overlap = min(region.x1, u.x1) - max(region.x0, u.x0)
            h_gap = max(u.x0 - region.x1, region.x0 - u.x1)
            v_gap = max(u.y0 - region.y1, region.y0 - u.y1)
            beside = v_overlap >= 0.5 * u.height and h_gap <= NEIGHBOUR_GAP
            stacked = h_overlap >= 0.5 * u.width and v_gap <= NEIGHBOUR_GAP   # chart + legend (9-36)
            if (beside or stacked) and no_caption_inside(region | u, captions, own_caption):
                region = region | u
                taken.add(i)
                grown = True
    return region, taken


def distance(a, b):
    """Gap between two rectangles (0 if they touch or overlap)."""
    dx = max(b.x0 - a.x1, a.x0 - b.x1, 0)
    dy = max(b.y0 - a.y1, a.y0 - b.y1, 0)
    return (dx * dx + dy * dy) ** 0.5


def absorb_labels(region, blocks, captions, own_caption, other_regions):
    """Add short text labels printed just outside the drawing ("30° bank" on
    Figure 8-5). The ink map ignores text, so labels at the edge were cut off."""
    drawing = pymupdf.Rect(region)             # labels are measured from the drawing itself,
    near = pymupdf.Rect(drawing.x0 - LABEL_GAP, drawing.y0 - LABEL_GAP,   # never from text
                        drawing.x1 + LABEL_GAP, drawing.y1 + LABEL_GAP)   # already added (no chaining)
    for r, t in blocks:
        if len(t) > LABEL_MAX_CHARS or CAPTION.match(t) or MENTION.search(t) or r in drawing:
            continue                           # prose mentioning a figure is never a label (4-7)
        if not near.intersects(r):
            continue
        if any(distance(o, r) <= distance(drawing, r) for o in other_regions):
            continue                           # closer to another figure: its label, not ours (4-8 axis)
        side = min(drawing.y1, r.y1) - max(drawing.y0, r.y0) > 0           # left/right label
        over = min(drawing.x1, r.x1) - max(drawing.x0, r.x0) > 0           # top/bottom label
        if (side or over) and no_caption_inside(region | r, captions, own_caption) \
                and not r.intersects(own_caption):
            region = region | r
    return region


def upright_angle(page, caption):
    """Degrees to turn a figure so that it reads upright, from the direction of
    its caption's text: 0 for a normal caption, 90 for a caption reading bottom
    to top (all 12 sideways charts in FAA-H-8083-15B, e.g. Figure 1-8)."""
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            if pymupdf.Rect(line["bbox"]).intersects(caption):
                dx, dy = line["dir"]
                if abs(dx) >= abs(dy):
                    return 0 if dx > 0 else 180
                return 90 if dy < 0 else 270
    return 0


def render_rect(region, caption, page, others=()):
    """The area saved as the figure image: the region plus a small margin.
    The margin never reaches into the figure's own caption (1-18, 10-1) nor
    into another figure (a line of 7-3's frame on the edge of 7-1)."""
    r = (region + (-PAD, -PAD, PAD, PAD)) & page.rect
    for block in ([caption] if caption is not None else []) + list(others):
        if not r.intersects(block) or region.intersects(block):
            continue
        if block.x0 >= region.x1:
            r.x1 = min(r.x1, block.x0)
        elif block.x1 <= region.x0:
            r.x0 = max(r.x0, block.x1)
        elif block.y0 >= region.y1:
            r.y1 = min(r.y1, block.y0)
        elif block.y1 <= region.y0:
            r.y0 = max(r.y0, block.y1)
    return r


def label_blocks(page):
    """Text blocks that look like figure labels: short and in a small font.
    FAA figure labels are 8-9 pt Arial; body text is 10-11 pt and headings
    12 pt, so a heading next to a figure ("Slow-Speed Flight" beside 4-11) is
    never taken as a label."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        spans = [s for line in b["lines"] for s in line["spans"] if s["text"].strip()]
        if not spans or max(s["size"] for s in spans) > LABEL_MAX_SIZE:
            continue
        text = " ".join(" ".join(s["text"] for s in spans).split())
        if len(text) <= LABEL_MAX_CHARS:
            out.append((pymupdf.Rect(b["bbox"]), text))
    return out


def find_figures(page, ink):
    """All the per-page work: returns the text blocks, the captions, the
    figure regions, and pairs (caption index -> region index)."""
    blocks = text_blocks(page)
    labels = label_blocks(page)
    captions = [(r, t) for r, t in blocks if CAPTION.match(t)]
    cap_rects = [r for r, _ in captions]
    boxes = split_at_captions(graphic_boxes(page, ink),
                              [r for r in cap_rects if not is_vertical(r)], ink)
    regions = merge_boxes(boxes, separators=cap_rects)
    regions = join_sideways_figure(captions, regions)
    pairs = bind(captions, regions)

    # Finish each bound figure: cut its caption out, take in the pieces and
    # labels that belong to it. Uncaptioned pieces that get absorbed disappear
    # from the unbound list.
    bound = set(pairs.values())
    free = [i for i in range(len(regions)) if i not in bound]
    absorbed = set()
    for ci, ri in pairs.items():
        crect = cap_rects[ci]
        region = trim_caption(regions[ri], crect, ink)
        for _ in range(2):                     # labels can bring the other half of a
            candidates = [regions[i] for i in free if i not in absorbed]   # figure within reach (4-9)
            index = [i for i in free if i not in absorbed]
            region, took = absorb_neighbours(region, candidates, cap_rects, crect)
            absorbed.update(index[k] for k in took)
            others = [regions[j] for j in range(len(regions)) if j != ri and j not in absorbed]
            region = absorb_labels(region, labels, cap_rects, crect, others)
        regions[ri] = trim_caption(region, crect, ink)
    keep = [i for i in range(len(regions)) if i not in absorbed]
    new_index = {old: new for new, old in enumerate(keep)}
    regions = [regions[i] for i in keep]
    pairs = {ci: new_index[ri] for ci, ri in pairs.items()}
    return blocks, captions, regions, pairs


def expand_mentions(text):
    """Figure numbers mentioned in a paragraph, including 'Figures 3-4 through 3-6'."""
    found = set(MENTION.findall(text))
    for c1, n1, c2, n2 in MENTION_RANGE.findall(text):
        if c1 == c2 and int(n1) < int(n2) <= int(n1) + 30:
            found.update(f"{c1}-{n}" for n in range(int(n1), int(n2) + 1))
    return found


def prepare_output(out):
    """Empty the figures/ and unbound/ folders before a run, so images from an
    earlier run can never mix with this one (on 28 Oct a v4 folder left in
    place made v5 save 1-1_p22.png next to the old 1-1.png: 691 files)."""
    for sub in ("figures", "unbound"):
        folder = out / sub
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.png"):
            try:
                old.unlink()
            except PermissionError:
                sys.exit(f"Cannot delete {old}: close any window showing this folder "
                         f"(File Explorer, OneDrive sync) and run again.")


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python ingestion/extract_figures.py <path-to-pdf>")
    pdf_path = Path(sys.argv[1])
    handbook_id = pdf_path.stem
    out = Path("data") / "extracted" / handbook_id
    prepare_output(out)

    doc = pymupdf.open(pdf_path)
    gfx_doc = pymupdf.open(pdf_path)           # second copy: text removed there for ink maps
    figures, unbound = [], []
    mentions = defaultdict(list)               # figure number -> referencing paragraphs
    seen_numbers = set()

    for page in doc:
        pdf_page = page.number + 1             # 1-based position in the file
        printed = printed_page_number(page)    # e.g. "3-12", cited to learners
        blocks, captions, regions, pairs = find_figures(page, ink_map(gfx_doc[page.number]))

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
            duplicate = number in seen_numbers
            if duplicate:
                record["warning"] = "duplicate figure number (continued figure?)"
            seen_numbers.add(number)
            if ci in pairs:
                region = regions[pairs[ci]]
                # The page suffix is only for a figure number that really appears
                # twice in this handbook (decided from the captions, not from
                # files left over in the folder).
                name = f"{number}_p{pdf_page}.png" if duplicate else f"{number}.png"
                png = out / "figures" / name
                angle = upright_angle(page, crect)
                zoom = RENDER_DPI / 72
                page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom).prerotate(angle),
                                clip=render_rect(region, crect, page,
                                                 [regions[j] for j in pairs.values() if j != pairs[ci]])).save(png)
                record.update(status="bound", bbox=[round(v, 1) for v in region],
                              rotation=angle,     # degrees the saved image was turned to read upright
                              image_path=str(png.relative_to(out)).replace("\\", "/"))
                # A crop that contains a full body paragraph probably took in
                # surrounding text: send it to the admin QA queue.
                if any(len(t) > LONG_PARAGRAPH and not CAPTION.match(t)
                       and (r & region).get_area() >= 0.5 * r.get_area()
                       for r, t in blocks):           # half a paragraph or more inside
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
                       "LONG_PARAGRAPH": LONG_PARAGRAPH,
                       "INK_DPI": INK_DPI, "INK_LEVEL": INK_LEVEL,
                       "NEIGHBOUR_GAP": NEIGHBOUR_GAP, "LABEL_GAP": LABEL_GAP,
                       "LABEL_MAX_SIZE": LABEL_MAX_SIZE},
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== EXTRACTION REPORT ===")
    for k, v in report.items():
        if k != "thresholds":
            print(f"{k:38}: {v}")
    print(f"Output folder                         : {out}")


if __name__ == "__main__":
    main()
