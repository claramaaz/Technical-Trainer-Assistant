"""Tests for ingestion/chunk_text.py, written from the rules in SPEC 5.1.

Run from the repository root:   python -m pytest -q tests/test_chunk_text.py

The fixture builds a small fake handbook with the same fonts as the FAA one
(Helvetica-Bold headings, Times-Roman 10 pt body text), runs the figure
extractor (the chunker needs its figures.jsonl) and then the chunker.

ONE example test is written below. The other cases are listed at the bottom
as TODO: write each one yourself (brief 11.3: "You write your own tests").
"""
import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parent.parent
BODY = "tiro"      # Times-Roman (body text)
H1 = "hebo"        # Helvetica-Bold (headings)
LONG = ("The pitot tube measures ram air pressure for the airspeed indicator. " * 6).strip()


def make_handbook(path):
    doc = pymupdf.open()

    def page(label):
        p = doc.new_page(width=594, height=774)           # the FAA page size
        p.insert_text((290, 760), label, fontname="helv", fontsize=10)    # printed page number (footer)
        return p

    # Front matter: no printed page number, must not be chunked.
    p = doc.new_page(width=594, height=774)
    p.insert_text((72, 100), "Preface text that is not part of any chapter.", fontname=BODY, fontsize=10)

    # Page 1-1: two sections; the second paragraph runs on to page 1-2.
    p = page("1-1")
    p.insert_text((72, 80), "Pitot-Static System", fontname=H1, fontsize=12)
    p.insert_textbox(pymupdf.Rect(72, 90, 540, 160), LONG + ".", fontname=BODY, fontsize=10)
    p.insert_text((72, 190), "Blocked Pitot Tube", fontname=H1, fontsize=10)
    p.insert_textbox(pymupdf.Rect(72, 200, 540, 260),
                     "If the pitot tube is blocked the airspeed indicator reads zero and the pilot",
                     fontname=BODY, fontsize=10)
    p.draw_rect(pymupdf.Rect(72, 400, 300, 600), fill=(0.6, 0.8, 1))            # a figure
    p.insert_text((72, 615), "Figure 1-1. A pitot tube.", fontname="hebo", fontsize=8)

    # Page 1-2: continuation of the paragraph (starts with a lower-case word).
    p = page("1-2")
    p.insert_textbox(pymupdf.Rect(72, 80, 540, 140),
                     "should check the pitot heat as shown in Figure 1-1.",
                     fontname=BODY, fontsize=10)

    # Page 2-1: a new chapter; its first paragraph has no heading of its own.
    p = page("2-1")
    p.insert_textbox(pymupdf.Rect(72, 80, 540, 140), "Chapter two text without a heading.",
                     fontname=BODY, fontsize=10)

    # Page I-1: the Index, never chunked.
    p = page("I-1")
    p.insert_textbox(pymupdf.Rect(72, 80, 540, 140), "airspeed indicator, 5-3", fontname=BODY, fontsize=10)
    doc.save(path)


@pytest.fixture(scope="module")
def chunks(tmp_path_factory):
    work = tmp_path_factory.mktemp("work")
    pdf = work / "TEST-HB.pdf"
    make_handbook(pdf)
    for script, *args in (("extract_figures.py", str(pdf)), ("chunk_text.py", "chunk", str(pdf))):
        run = subprocess.run([sys.executable, str(ROOT / "ingestion" / script), *args],
                             cwd=work, capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
    out = work / "data" / "extracted" / "TEST-HB" / "chunks.jsonl"
    return [json.loads(line) for line in open(out, encoding="utf-8")]


def test_paragraph_continued_on_next_page_is_one_chunk_with_both_pages(chunks):
    # SPEC 5.1 rule 2: a paragraph is never split, and the chunk stores the
    # pages it covers (provenance).
    c = next(c for c in chunks if "reads zero" in c["text"])
    assert "and the pilot should check the pitot heat" in c["text"]   # one sentence, not two paragraphs
    assert c["printed_pages"] == ["1-1", "1-2"]


# TODO (write each test yourself, one rule per test):
# 1. A chunk never crosses a heading: no chunk contains both "ram air pressure"
#    and "reads zero" (they are in two different sections).
# 2. heading_path of the "reads zero" chunk is ["Pitot-Static System", "Blocked Pitot Tube"],
#    and its embed_text starts with that heading path.
# 3. Headings do not carry over into a new chapter: the chunk with "Chapter two text"
#    has chapter "2" and an empty heading_path.
# 4. The front matter ("Preface") and the Index ("airspeed indicator, 5-3") appear in no chunk.
# 5. The figure caption "A pitot tube" is in no chunk (figures and captions are skipped).
# 6. figure_mentions of the "reads zero" chunk is ["1-1"].
# 7. Cap: no chunk is longer than 200 words unless it is a single paragraph.
#    (Hint: add a section with many short paragraphs to make_handbook, then check
#    that every chunk has words <= 200 or contains no blank line "\n\n".)

def test_chunk_never_crosses_a_heading(chunks):
    # SPEC 5.1 rule 1: a chunk never runs across a heading.
    for c in chunks:
        assert not ("ram air pressure" in c["text"] and "reads zero" in c["text"])


def test_heading_path_and_embed_text(chunks):
    # The chunk remembers the headings above it, and the text sent to the
    # embedding model starts with them (SPEC 5.1).
    c = next(c for c in chunks if "reads zero" in c["text"])
    assert c["heading_path"] == ["Pitot-Static System", "Blocked Pitot Tube"]
    assert c["embed_text"].startswith("Pitot-Static System > Blocked Pitot Tube")


def test_headings_do_not_carry_over_into_a_new_chapter(chunks):
    # Chapter 2 starts with text that has no heading of its own: it must not
    # inherit "Blocked Pitot Tube" from chapter 1.
    c = next(c for c in chunks if "Chapter two text" in c["text"])
    assert c["chapter"] == "2"
    assert c["heading_path"] == []


def test_front_matter_and_index_are_not_chunked(chunks):
    # Only chapter body text is searchable: no preface, no index.
    all_text = " ".join(c["text"] for c in chunks)
    assert "Preface" not in all_text
    assert "airspeed indicator, 5-3" not in all_text


def test_figure_captions_are_not_chunked(chunks):
    # Captions belong to the figures (figures.jsonl), not to the text chunks.
    assert not any("A pitot tube" in c["text"] for c in chunks)


def test_figure_mentions_are_recorded(chunks):
    # "as shown in Figure 1-1" links the passage to its figure.
    c = next(c for c in chunks if "reads zero" in c["text"])
    assert c["figure_mentions"] == ["1-1"]