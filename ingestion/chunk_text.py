"""Split a handbook's body text into chunks for retrieval (SPEC 5.1).

Usage (from the repository root; run extract_figures.py first, because the
chunker skips the figures and captions it found):
    python ingestion/chunk_text.py measure data/raw/FAA-H-8083-15B.pdf
    python ingestion/chunk_text.py chunk   data/raw/FAA-H-8083-15B.pdf

Rules (SPEC 5.1):
 1. Text is split at section headings; a chunk never crosses a heading.
 2. Inside a section, whole paragraphs are grouped up to CHUNK_WORDS words;
    a paragraph is never split. A paragraph longer than the cap becomes a
    chunk of its own.
 3. Each chunk stores handbook, chapter, heading path and the pages it covers.
    `embed_text` = heading path + text: the heading gives the chunk its topic.
 4. No overlap between chunks.

How the PDF is read (FAA-H-8083-15B, measured 28 Oct):
  - headings are lines in Helvetica-Bold 12 pt (level 1), Helvetica-Bold 10 pt
    (level 2) or Times-BoldItalic 11 pt (level 3); body text is Times 10 pt;
  - a heading often shares a text block with the paragraph after it, so the
    text is read line by line, not block by block;
  - a paragraph that runs on into the next column or page (no full stop at
    the end) is joined back together;
  - pages count only if they carry a printed page number such as "4-8",
    "A-1" or "G-7"; front matter has none and the Index ("I-1") is skipped;
  - figures, their captions and the header/footer bands are skipped.

Output, in data/extracted/<handbook-id>/:
    chunks.jsonl        one chunk per line
    chunk_report.json   counts and sizes
"""
import json
import re
import statistics
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_figures import expand_mentions  # same "Figure 4-12" reader as the extractor

CHUNK_WORDS = 200        # chosen 28 Oct from the measurement (SPEC 5.1)
HEADER_ZONE = 0.06       # top 6 % of the page: running header / page number
FOOTER_ZONE = 0.92       # bottom 8 %: footer / page number
SKIP_LABELS = {"I"}      # Index pages: lists of page numbers, not content
PART_NAMES = {"A": "Appendix A", "B": "Appendix B", "G": "Glossary"}   # headings for lettered parts
PAGE_LABEL = re.compile(r"^(\d+|[A-Z])-(\d+)$")
DOT_LEADER = re.compile(r"\.{5,}")             # "Fan Marker........FM": a list, not prose
SENTENCE_END = re.compile(r'[.:?!)\]”"]$')


def page_label(page):
    """The page number printed on the page ("4-8", "A-1", "G-7"), or ""."""
    H = page.rect.height
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        if y1 <= H * HEADER_ZONE + 10 or y0 >= H * FOOTER_ZONE:
            for line in text.splitlines():
                if PAGE_LABEL.match(line.strip()):
                    return line.strip()
    return ""


def line_kind(spans):
    """'heading' with its level, 'body', or 'other' for one line of text."""
    font, size = spans[0]["font"], spans[0]["size"]
    text = "".join(s["text"] for s in spans).strip()
    same_font = all(s["font"] == font for s in spans)
    if same_font and len(text) < 90:
        if font.startswith("Helvetica-Bold") and 11.5 <= size <= 12.5:
            return "heading", 1
        if font.startswith("Helvetica-Bold") and 9.5 <= size < 11.5:
            return "heading", 2
        if font == "Times-BoldItalic" and 10.5 <= size <= 11.5:
            return "heading", 3
    if font.startswith("Times") and 9.5 <= size <= 10.5:
        return "body", 0
    return "other", 0


def figure_areas(figures_path):
    """pdf page -> rectangles of figures and captions (from extract_figures)."""
    areas = {}
    for line in open(figures_path, encoding="utf-8"):
        f = json.loads(line)
        rects = [f["caption_bbox"]] + ([f["bbox"]] if f.get("bbox") else [])
        areas.setdefault(f["pdf_page"], []).extend(pymupdf.Rect(r) for r in rects)
    return areas


def read_events(doc, areas):
    """Walk the body text in reading order. Yields ("chapter", name),
    ("heading", level, text) and ("line", text, pdf_page, label, new_block)."""
    chapter = None
    for page in doc:
        label = page_label(page)
        if not label or label.split("-")[0] in SKIP_LABELS:
            continue
        if label.split("-")[0] != chapter:    # headings never carry over into a new chapter
            chapter = label.split("-")[0]
            yield ("chapter", PART_NAMES.get(chapter))
        H = page.rect.height
        skip = areas.get(page.number + 1, [])
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            r = pymupdf.Rect(b["bbox"])
            if r.y1 < H * HEADER_ZONE or r.y0 > H * FOOTER_ZONE:
                continue
            if any((r & a).get_area() > 0.5 * r.get_area() for a in skip):
                continue                       # inside a figure or a caption
            new_block = True
            for line in b["lines"]:
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                kind, level = line_kind(spans)
                text = " ".join("".join(s["text"] for s in spans).split())
                if kind == "heading":
                    yield ("heading", level, text)
                    new_block = True
                elif kind == "body":
                    yield ("line", text, page.number + 1, label, new_block)
                    new_block = False


def build_sections(events):
    """Group lines into paragraphs and paragraphs into sections.
    A section = (heading path, [paragraph, ...]); a paragraph is a dict with
    its text and the pages it covers."""
    sections, path, paras = [], [], []

    def close():
        if paras:
            sections.append((list(path), list(paras)))
        paras.clear()

    for ev in events:
        if ev[0] == "chapter":
            close()
            path[:] = [(0, ev[1])] if ev[1] else []
            continue
        if ev[0] == "heading":
            _, level, text = ev
            close()
            path[:] = [h for h in path if h[0] < level] + [(level, text)]
            continue
        _, text, pdf_page, label, new_block = ev
        continues = paras and not SENTENCE_END.search(paras[-1]["text"])
        if new_block and not continues:
            paras.append({"text": text, "pages": [(pdf_page, label)]})
        else:
            if not paras:
                paras.append({"text": text, "pages": [(pdf_page, label)]})
                continue
            p = paras[-1]
            p["text"] += " " + text
            if (pdf_page, label) not in p["pages"]:
                p["pages"].append((pdf_page, label))
    close()
    # Lists with dot leaders (table of contents style) are not prose.
    out = []
    for path_, ps in sections:
        ps = [p for p in ps if not DOT_LEADER.search(p["text"])]
        if ps:
            out.append(([t for _, t in path_], ps))
    return out


def words(text):
    return len(text.split())


def make_chunks(sections, handbook_id, cap=CHUNK_WORDS):
    chunks = []
    for path, paras in sections:
        group = []
        for p in paras:
            if group and sum(words(g["text"]) for g in group) + words(p["text"]) > cap:
                chunks.append((path, group))
                group = []
            group.append(p)
        if group:
            chunks.append((path, group))
    out = []
    for n, (path, group) in enumerate(chunks, 1):
        text = "\n\n".join(g["text"] for g in group)
        pages = sorted({pg for g in group for pg in g["pages"]})
        labels = [label for _, label in pages]
        heading = " > ".join(path) if path else ""
        out.append({
            "chunk_id": f"{handbook_id}-c{n:04d}",
            "handbook_id": handbook_id,
            "chapter": labels[0].split("-")[0],
            "heading_path": path,
            "text": text,
            "embed_text": f"{heading}\n\n{text}" if heading else text,
            "words": words(text),
            "pdf_pages": [pp for pp, _ in pages],
            "printed_pages": labels,
            "figure_mentions": sorted(expand_mentions(text)),
        })
    return out


def load(pdf_path):
    handbook_id = pdf_path.stem
    figures = Path("data") / "extracted" / handbook_id / "figures.jsonl"
    if not figures.exists():
        sys.exit(f"{figures} not found: run ingestion/extract_figures.py first.")
    doc = pymupdf.open(pdf_path)
    return handbook_id, build_sections(read_events(doc, figure_areas(figures)))


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def measure(pdf_path):
    _, sections = load(pdf_path)
    pw = [words(p["text"]) for _, ps in sections for p in ps]
    if not pw:
        sys.exit("No body text found (see the chunk command's message).")
    print(f"{len(sections)} sections, {len(pw)} paragraphs, {sum(pw)} words")
    print(f"paragraph words: median {statistics.median(pw)}, p90 {pct(pw, .9)}, "
          f"p99 {pct(pw, .99)}, max {max(pw)}")
    print("cap | chunks | median words | paragraphs longer than the cap")
    for cap in (150, 200, 250):
        cw = [c["words"] for c in make_chunks(sections, "x", cap)]
        print(f"{cap} | {len(cw)} | {statistics.median(cw)} | {sum(1 for w in pw if w > cap)}")


def chunk(pdf_path):
    handbook_id, sections = load(pdf_path)
    chunks = make_chunks(sections, handbook_id)
    if not chunks:
        sys.exit("No body text found: no page carries a printed page number such as 4-8, "
                 "or the fonts differ from FAA-H-8083-15B (see line_kind).")
    out = Path("data") / "extracted" / handbook_id
    with open(out / "chunks.jsonl", "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    cw = [c["words"] for c in chunks]
    report = {
        "handbook_id": handbook_id,
        "chunk_words_cap": CHUNK_WORDS,
        "sections": len(sections),
        "paragraphs": sum(len(ps) for _, ps in sections),
        "chunks": len(chunks),
        "chunk_words_median": statistics.median(cw),
        "chunk_words_max": max(cw),
        "chunks_over_cap_single_paragraph": sum(1 for w in cw if w > CHUNK_WORDS),
        "chunks_spanning_two_pages_or_more": sum(1 for c in chunks if len(c["pdf_pages"]) > 1),
        "chunks_mentioning_a_figure": sum(1 for c in chunks if c["figure_mentions"]),
        "chapters": sorted({c["chapter"] for c in chunks}, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 0, x)),
    }
    (out / "chunk_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("=== CHUNK REPORT ===")
    for k, v in report.items():
        print(f"{k:36}: {v}")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("measure", "chunk"):
        sys.exit("Usage: python ingestion/chunk_text.py measure|chunk <path-to-pdf>")
    (measure if sys.argv[1] == "measure" else chunk)(Path(sys.argv[2]))


if __name__ == "__main__":
    main()
