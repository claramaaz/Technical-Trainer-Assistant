"""Tests for ingestion/extract_figures.py on a small synthetic handbook.

Run from the repository root:   python -m pytest -q
The PDF is generated on the fly, so no FAA file is needed for the tests.
"""
import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parent.parent


def make_handbook(path):
    doc = pymupdf.open()
    grey = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), 0)
    grey.clear_with(180)

    def footer(page, number):
        page.draw_line((50, 30), (560, 30))                       # header rule: must be ignored
        page.insert_text((290, page.rect.height - 25), number)    # printed page number

    # Page 1: raster figure 1-1 + paragraph mentioning a range of figures.
    p = doc.new_page()
    footer(p, "1-1")
    p.insert_text((72, 80), "Figures 1-1 through 1-3 show the attitude indicator.")
    p.insert_image(pymupdf.Rect(72, 120, 320, 320), pixmap=grey)
    p.insert_text((72, 340), "Figure 1-1. Attitude indicator.")

    # Page 2: VECTOR-only figure 1-2 made of several pieces + a small logo (ignored).
    p = doc.new_page()
    footer(p, "1-2")
    p.draw_circle((200, 220), 80)
    p.draw_line((120, 220), (280, 220))
    p.draw_rect(pymupdf.Rect(150, 300, 250, 330))                # separate piece, within MERGE_GAP? no: joined by line below
    p.draw_line((200, 300), (200, 290))
    p.insert_text((72, 360), "Figure 1-2. Gyroscope.")
    p.insert_image(pymupdf.Rect(500, 700, 520, 720), pixmap=grey)  # 20 pt logo: too small

    # Page 3: caption with no drawing (caption_only) + an uncaptioned image (unbound).
    p = doc.new_page()
    footer(p, "1-3")
    p.insert_text((72, 100), "Figure 1-3. Missing artwork.")
    p.insert_image(pymupdf.Rect(72, 400, 300, 600), pixmap=grey)
    p.insert_text((72, 650), "As Figure 1-2 shows, the gyro stays rigid in space.")
    # Page 4: two figures 10 pt apart, the first caption between them (must NOT merge).
    p = doc.new_page()
    footer(p, "1-4")
    p.draw_rect(pymupdf.Rect(72, 60, 520, 180), fill=(0.6, 0.8, 1))
    p.insert_text((72, 192), "Figure 1-4. Top figure.")
    p.draw_rect(pymupdf.Rect(320, 190, 520, 400), fill=(0.6, 0.8, 1))
    p.insert_text((320, 415), "Figure 1-5. Right figure.")

    # Page 5: landscape figure printed sideways, caption rotated on the right.
    p = doc.new_page()
    footer(p, "1-5")
    p.draw_rect(pymupdf.Rect(72, 60, 500, 340), fill=(0.9, 0.9, 0.6))
    p.draw_rect(pymupdf.Rect(72, 400, 500, 700), fill=(0.9, 0.9, 0.6))
    p.insert_text((540, 700), "Figure 1-6. Sideways chart pair.", rotate=90)

    # Page 6: a path drawn far larger than its clip (only the clipped part is
    # visible). show_pdf_page places a source page inside a clipped box, the
    # same structure the FAA PDFs use for figure artwork.
    art = pymupdf.open()
    a = art.new_page(width=600, height=900)
    a.draw_rect(pymupdf.Rect(5, 5, 595, 895))              # huge frame, mostly clipped away
    a.draw_rect(pymupdf.Rect(200, 300, 400, 600), fill=(0.7, 0.7, 0.7))
    p = doc.new_page()
    footer(p, "1-6")
    p.insert_text((72, 100), "Body text that must stay out of the figure. " * 2)
    p.show_pdf_page(pymupdf.Rect(150, 300, 400, 500), art, 0,
                    clip=pymupdf.Rect(150, 250, 450, 650))
    p.insert_text((150, 515), "Figure 1-7. Clipped artwork.")
    doc.save(path)


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    work = tmp_path_factory.mktemp("work")
    pdf = work / "TEST-HB.pdf"
    make_handbook(pdf)
    run = subprocess.run([sys.executable, str(ROOT / "ingestion" / "extract_figures.py"), str(pdf)],
                         cwd=work, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    out = work / "data" / "extracted" / "TEST-HB"
    figures = {f["figure_number"]: f for f in map(json.loads, open(out / "figures.jsonl"))}
    unbound = [json.loads(l) for l in open(out / "unbound.jsonl")]
    report = json.loads((out / "report.json").read_text())
    return out, figures, unbound, report


def test_counts(result):
    _, _, _, report = result
    assert report["captions_found"] == 7
    assert report["figures_bound_to_caption"] == 6
    assert report["captions_without_region"] == 1
    assert report["unbound_regions"] == 1


def test_raster_figure_bound_with_provenance(result):
    out, figures, _, _ = result
    f = figures["1-1"]
    assert f["status"] == "bound"
    assert f["pdf_page"] == 1 and f["printed_page"] == "1-1"
    assert (out / f["image_path"]).exists()


def test_vector_figure_is_found(result):
    _, figures, _, _ = result
    assert figures["1-2"]["status"] == "bound"     # no image object on that page


def test_caption_without_artwork_goes_to_qa(result):
    _, figures, _, _ = result
    assert figures["1-3"]["status"] == "caption_only"


def test_uncaptioned_image_is_unbound(result):
    _, _, unbound, _ = result
    assert unbound[0]["pdf_page"] == 3


def test_referencing_paragraphs(result):
    _, figures, _, _ = result
    pages_1_2 = [r["pdf_page"] for r in figures["1-2"]["referencing_paragraphs"]]
    assert pages_1_2 == [1, 3]                      # range on p.1, direct mention on p.3
    assert len(figures["1-3"]["referencing_paragraphs"]) == 1


def test_caption_between_figures_prevents_merge(result):
    _, figures, _, _ = result
    top, right = figures["1-4"], figures["1-5"]
    assert top["status"] == right["status"] == "bound"
    assert top["bbox"][3] < 185 and right["bbox"][1] > 185   # two separate regions


def test_sideways_caption_takes_whole_landscape_figure(result):
    _, figures, _, _ = result
    f = figures["1-6"]
    assert f["status"] == "bound"
    assert f["bbox"][1] < 70 and f["bbox"][3] > 690          # both charts, one figure


def test_clipped_artwork_does_not_swallow_text(result):
    _, figures, _, _ = result
    f = figures["1-7"]
    assert f["status"] == "bound"
    assert f["bbox"][1] >= 290                               # body text at y=100 excluded
    assert "needs_review" not in f
