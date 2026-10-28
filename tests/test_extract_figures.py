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

    # Page 7: an image placed far larger than what is visible (clipped). Its
    # hidden part hangs sideways over a column of body text, like Figure 9-19
    # in FAA-H-8083-15B (an image 693 pt wide on a 594 pt page).
    photo = pymupdf.open()
    ph = photo.new_page(width=600, height=200)
    ph.insert_image(pymupdf.Rect(0, 0, 600, 200), pixmap=grey, keep_proportion=False)
    p = doc.new_page()
    footer(p, "1-7")
    p.show_pdf_page(pymupdf.Rect(72, 80, 272, 280), photo, 0,
                    clip=pymupdf.Rect(0, 0, 200, 200))           # visible: x 72..272 only
    p.insert_textbox(pymupdf.Rect(300, 80, 540, 280), "Body paragraph. " * 25)
    p.insert_text((72, 300), "Figure 1-8. Oversized image.")

    # Page 8: ONE image whose picture shows two figures, with a caption in
    # the white gap between them (like Figure 11-13 on PDF page 336).
    rows = [bytes([120] * 300) if (y < 80 or y >= 120) else bytes([255] * 300)
            for y in range(200)]                               # grey / white / grey bands
    two = pymupdf.Pixmap(pymupdf.csRGB, 100, 200, b"".join(rows), 0)
    p = doc.new_page()
    footer(p, "1-8")
    p.insert_image(pymupdf.Rect(72, 60, 372, 660), pixmap=two)
    p.insert_text((72, 330), "Figure 1-9. Upper half.")
    p.insert_text((72, 680), "Figure 1-10. Lower half.")

    # Page 9: two figures side by side, 6 pt apart, each with its own caption
    # below it (Figures 5-37 / 5-38 in FAA-H-8083-15B). Must stay separate.
    p = doc.new_page()
    footer(p, "1-9")
    p.draw_rect(pymupdf.Rect(72, 60, 300, 195), fill=(0.6, 0.8, 1))
    p.draw_rect(pymupdf.Rect(306, 60, 540, 195), fill=(0.6, 0.8, 1))
    p.insert_text((72, 207), "Figure 1-11. Left.")
    p.insert_text((306, 217), "Figure 1-12. Right.")

    # Page 10: a figure whose text labels sit just outside the drawing, and a
    # small separate piece 30 pt to its left (Figures 8-5 and 6-20).
    p = doc.new_page()
    footer(p, "1-10")
    p.draw_rect(pymupdf.Rect(80, 100, 120, 160), fill=(0.3, 0.3, 0.3))   # side piece
    p.draw_rect(pymupdf.Rect(150, 80, 400, 300), fill=(0.6, 0.8, 1))    # main drawing
    p.insert_text((410, 150), "30 bank", fontsize=8)                     # label outside (8 pt, like FAA)
    p.insert_text((150, 312), "Slow-Speed Flight", fontsize=12)          # a heading: never a label
    p.insert_text((150, 330), "Figure 1-13. Labelled figure.")

    # Page 11: a framed chart with a sideways caption INSIDE the frame
    # (Figures 1-18, 1-19): the caption must not be part of the image.
    p = doc.new_page()
    footer(p, "1-11")
    p.draw_rect(pymupdf.Rect(40, 50, 560, 720))                          # frame
    p.draw_rect(pymupdf.Rect(60, 70, 500, 700), fill=(0.9, 0.9, 0.6))   # chart
    p.insert_text((540, 700), "Figure 1-14. Framed sideways chart.", rotate=90)
    p.insert_text((22, 400), "N", fontsize=8)                            # 8 pt label left of the frame

    # Page 12: an image placed far larger than shown, whose hidden part
    # reaches over the NEXT figure in the other column (PDF page 138/195).
    wide = pymupdf.open()
    w = wide.new_page(width=600, height=200)
    w.insert_image(pymupdf.Rect(0, 0, 600, 200), pixmap=grey, keep_proportion=False)
    p = doc.new_page()
    footer(p, "1-12")
    p.show_pdf_page(pymupdf.Rect(72, 80, 272, 280), wide, 0,
                    clip=pymupdf.Rect(0, 0, 200, 200))           # visible: x 72..272
    p.insert_image(pymupdf.Rect(320, 80, 520, 200), pixmap=grey, keep_proportion=False)
    p.insert_text((72, 295), "Figure 1-15. Oversized left image.")
    p.insert_text((320, 212), "Figure 1-16. Right image.")

    # Page 13: a two-panel figure, panels 50 pt apart, an axis label between
    # them close to the left panel (Figure 4-9: jet / propeller panels).
    p = doc.new_page()
    footer(p, "1-13")
    p.draw_rect(pymupdf.Rect(72, 80, 250, 200), fill=(0.6, 0.8, 1))
    p.draw_rect(pymupdf.Rect(300, 80, 480, 200), fill=(0.6, 0.8, 1))
    p.insert_text((256, 140), "Power", fontsize=8)
    p.insert_text((72, 222), "Figure 1-17. Two panels.")

    # Page 14: a huge image placed over the whole page but visible only at the
    # bottom, and a small real picture near the top (the sky of Figure 7-47).
    big = pymupdf.open()
    bg = big.new_page(width=524, height=600)
    bg.insert_image(pymupdf.Rect(0, 0, 524, 600), pixmap=grey, keep_proportion=False)
    p = doc.new_page()
    footer(p, "1-14")
    p.show_pdf_page(pymupdf.Rect(36, 400, 560, 600), big, 0,
                    clip=pymupdf.Rect(0, 300, 524, 500))         # visible: y 400..600
    p.insert_image(pymupdf.Rect(72, 110, 272, 150), pixmap=grey, keep_proportion=False)
    p.insert_text((72, 165), "Figure 1-18. Small picture under a huge one.")
    p.insert_text((36, 615), "Figure 1-19. The huge picture's visible part.")

    # Page 15: a THIN strip placed partly off the page (smaller in area than
    # its neighbour) that overlaps the bottom of the next figure (PDF page 138).
    strip = pymupdf.open()
    st = strip.new_page(width=628, height=30)
    st.insert_image(pymupdf.Rect(0, 0, 628, 30), pixmap=grey, keep_proportion=False)
    p = doc.new_page()
    footer(p, "1-15")
    p.insert_image(pymupdf.Rect(72, 150, 272, 280), pixmap=grey, keep_proportion=False)
    p.show_pdf_page(pymupdf.Rect(72, 280, 272, 310), strip, 0,
                    clip=pymupdf.Rect(0, 0, 200, 30))            # visible: x 72..272
    p.insert_image(pymupdf.Rect(320, 80, 540, 300), pixmap=grey, keep_proportion=False)
    p.insert_text((72, 325), "Figure 1-20. Left, with a strip.")
    p.insert_text((320, 316), "Figure 1-21. Right.")

    # Page 16: two panels side by side, each with its own caption (7-1 / 7-3).
    # The left one is drawn as two overlapping pieces; the right figure must
    # not take the left one's spare piece.
    p = doc.new_page()
    footer(p, "1-16")
    p.draw_rect(pymupdf.Rect(36, 380, 270, 680), fill=(0.6, 0.8, 1))
    p.draw_rect(pymupdf.Rect(150, 380, 270, 520), fill=(0.3, 0.5, 0.8))
    p.draw_rect(pymupdf.Rect(36, 478, 287, 504), fill=(0.3, 0.3, 0.3))  # strip 3 pt into the right panel
    p.draw_rect(pymupdf.Rect(284, 380, 520, 680), fill=(0.6, 0.8, 1))
    # two-line captions side by side, like 7-1 / 7-3 (one-line ones would be read as one block)
    p.insert_textbox(pymupdf.Rect(36, 687, 275, 725),
                     "Figure 1-22. Left panel of a pair, with a caption long enough to wrap.", fontsize=9)
    p.insert_textbox(pymupdf.Rect(285, 686, 524, 724),
                     "Figure 1-23. Right panel of a pair, with a caption long enough to wrap.", fontsize=9)
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
    assert report["captions_found"] == 23
    assert report["figures_bound_to_caption"] == 22
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


def test_oversized_image_cut_to_visible_part(result):
    _, figures, _, _ = result
    f = figures["1-8"]
    assert f["status"] == "bound"
    assert f["bbox"][2] < 290                                # stops before the text column
    assert "needs_review" not in f


def test_one_image_holding_two_figures_is_split_at_caption(result):
    _, figures, _, _ = result
    upper, lower = figures["1-9"], figures["1-10"]
    assert upper["status"] == lower["status"] == "bound"
    assert upper["bbox"][3] < 330 < lower["bbox"][1]          # one figure each side of the caption


def test_side_by_side_figures_with_own_captions_stay_apart(result):
    _, figures, _, _ = result
    left, right = figures["1-11"], figures["1-12"]
    assert left["bbox"][2] < 303 < right["bbox"][0]


def test_labels_and_side_pieces_are_included(result):
    _, figures, _, _ = result
    box = figures["1-13"]["bbox"]
    assert box[0] <= 80                     # the separate piece on the left
    assert box[2] >= 430                    # the "30 bank" label on the right
    assert box[3] < 302                     # but not the 12 pt heading below it


def test_caption_inside_frame_is_cut_out(result):
    _, figures, _, _ = result
    f = figures["1-14"]
    assert f["status"] == "bound"
    assert f["bbox"][2] <= f["caption_bbox"][0]
    assert f["bbox"][0] <= 23               # the label outside the frame survives the cut


def test_saved_image_margin_stops_at_caption():
    sys.path.insert(0, str(ROOT / "ingestion"))
    import extract_figures as E
    page = pymupdf.open().new_page()
    region = pymupdf.Rect(72, 100, 300, 300)
    below = pymupdf.Rect(72, 302, 200, 312)                 # caption 2 pt below the figure
    side = pymupdf.Rect(302, 100, 312, 300)                 # sideways caption 2 pt right
    assert E.render_rect(region, below, page).y1 <= below.y0
    assert E.render_rect(region, side, page).x1 <= side.x0
    neighbour = pymupdf.Rect(304, 100, 500, 300)            # another figure 4 pt to the right
    assert E.render_rect(region, None, page, [neighbour]).x1 <= neighbour.x0


def test_oversized_image_does_not_take_the_next_figure(result):
    _, figures, _, _ = result
    left, right = figures["1-15"], figures["1-16"]
    assert left["status"] == right["status"] == "bound"
    assert left["bbox"][2] < 300 and right["bbox"][0] > 300


def test_two_panel_figure_joined_through_its_labels(result):
    _, figures, _, _ = result
    box = figures["1-17"]["bbox"]
    assert box[0] <= 72 and box[2] >= 480


def test_second_run_replaces_the_first(tmp_path):
    """Running twice into the same folder gives the same files, no _pNN copies."""
    pdf = tmp_path / "TEST-HB.pdf"
    make_handbook(pdf)
    for _ in range(2):
        run = subprocess.run([sys.executable, str(ROOT / "ingestion" / "extract_figures.py"), str(pdf)],
                             cwd=tmp_path, capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
    names = sorted(p.name for p in (tmp_path / "data" / "extracted" / "TEST-HB" / "figures").glob("*.png"))
    assert len(names) == 22
    assert not any("_p" in n for n in names)


def test_small_picture_under_a_huge_invisible_one_is_kept(result):
    _, figures, _, _ = result
    f = figures["1-18"]
    assert f["status"] == "bound"
    assert f["bbox"][1] < 115 and f["bbox"][3] < 160


def test_thin_offpage_strip_does_not_take_the_next_figure(result):
    _, figures, _, _ = result
    left, right = figures["1-20"], figures["1-21"]
    assert left["bbox"][2] < 300 and right["bbox"][0] > 300


def test_sideways_figure_is_saved_upright(result):
    out, figures, _, _ = result
    f = figures["1-6"]                          # caption printed bottom-to-top
    assert f["rotation"] == 90
    w, h = pymupdf.Pixmap(str(out / f["image_path"])).width, pymupdf.Pixmap(str(out / f["image_path"])).height
    assert w > h                                # the tall region became a wide image
    assert figures["1-1"]["rotation"] == 0


def test_side_by_side_panels_do_not_take_each_others_pieces(result):
    _, figures, _, _ = result
    assert figures["1-22"]["status"] == figures["1-23"]["status"] == "bound"
    assert figures["1-23"]["bbox"][0] > 275 and figures["1-22"]["bbox"][2] <= 281   # no sliver of the right panel
