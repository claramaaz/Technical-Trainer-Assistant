"""Tests for the stored page images of "View source" (P7-47; SPEC UC-07 step 3, alternative A1).

A made-up 5-page handbook in a temporary database (tests/test_load_db.py) and a 5-page PDF made
with PyMuPDF, so no real handbook is needed. Skipped if PostgreSQL is not running.
Run:   python -m pytest -q tests/test_page_images.py
"""
import fitz
import pytest
from fastapi.testclient import TestClient

import load_db
import render_pages
from backend import app as app_module
from backend import retrieval
from test_load_db import HID, MODEL, make_handbook
from test_retrieval_db import FIGURE_VECTORS

JPEG = b"\xff\xd8\xff"


@pytest.fixture
def handbook(db, tmp_path):
    make_handbook(tmp_path)                       # pages 1..5; figure 1-1 is on PDF page 3
    load_db.load(db, load_db.read_sources(HID, MODEL, tmp_path))
    db.commit()
    with fitz.open() as pdf:
        for n in range(1, 6):
            pdf.new_page().insert_text((72, 72), f"page {n}")
        pdf.save(tmp_path / "data" / "raw" / f"{HID}.pdf")
    return tmp_path


def keys(db):
    db.commit()
    return dict(db.execute("SELECT pdf_index, image_path FROM pages WHERE document_id = %s", (HID,)).fetchall())


def test_every_page_is_rendered_and_recorded(db, handbook):
    assert render_pages.render_handbook(db, HID, root=handbook) == {"rendered": 5, "skipped": 0}
    stored = keys(db)
    assert stored == {i: f"{HID}/pages/p{i:04d}.jpg" for i in range(1, 6)}
    for key in stored.values():
        assert (handbook / "data" / "extracted" / key).read_bytes()[:3] == JPEG


def test_second_run_renders_nothing(db, handbook):
    render_pages.render_handbook(db, HID, root=handbook)
    assert render_pages.render_handbook(db, HID, root=handbook) == {"rendered": 0, "skipped": 5}


def test_pdf_with_fewer_pages_than_the_database_is_refused(db, handbook):
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(handbook / "data" / "raw" / f"{HID}.pdf")
    with pytest.raises(ValueError):
        render_pages.render_handbook(db, HID, root=handbook)


def search_figure_1_1(pg_test_dsn, handbook, monkeypatch):
    index = retrieval.load_index_from(pg_test_dsn, image_root=handbook / "data" / "extracted")
    monkeypatch.setattr(retrieval, "load_index", lambda: index)
    return retrieval.retrieve("anything", k=1, index=index, query_vector=FIGURE_VECTORS[0])["results"][0]


def test_result_gives_the_page_image_of_its_own_page_and_the_pdf_link(db, pg_test_dsn, handbook, monkeypatch):
    render_pages.render_handbook(db, HID, root=handbook)
    result = search_figure_1_1(pg_test_dsn, handbook, monkeypatch)
    assert result["figure_id"] == "1-1"
    assert result["page_image_url"] == f"/figures/{result['id']}/page-image"
    assert result["source_pdf_url"] == "https://example.org/test.pdf#page=3"   # PDF page, not printed page
    path = retrieval.page_image_path_for(result["id"])
    assert path.name == "p0003.jpg"


def test_page_not_rendered_gives_no_page_image_but_keeps_the_pdf_link(db, pg_test_dsn, handbook, monkeypatch):
    result = search_figure_1_1(pg_test_dsn, handbook, monkeypatch)   # render_pages not run (UC-07 A1)
    assert result["page_image_url"] is None
    assert result["source_pdf_url"] == "https://example.org/test.pdf#page=3"
    assert retrieval.page_image_path_for(result["id"]) is None


def test_page_image_route(db, pg_test_dsn, handbook, monkeypatch):
    render_pages.render_handbook(db, HID, root=handbook)
    result = search_figure_1_1(pg_test_dsn, handbook, monkeypatch)
    client = TestClient(app_module.app)
    r = client.get(result["page_image_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:3] == JPEG
    for bad in ["999999", "1-1", "..%2F..%2FREADME.md"]:
        assert client.get(f"/figures/{bad}/page-image").status_code == 404
