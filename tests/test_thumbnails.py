"""Tests for the figure thumbnails (P7-49), written from SPEC NFR-001: "Figures are first shown as
compressed thumbnails; the full-size image loads on request."

A made-up handbook in a temporary database (tests/test_load_db.py) with large fake PNG figures.
Skipped if PostgreSQL is not running.   Run:   python -m pytest -q tests/test_thumbnails.py
"""
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import load_db
import make_thumbnails
from backend import app as app_module
from backend import retrieval
from test_load_db import HID, MODEL, make_handbook
from test_retrieval_db import FIGURE_VECTORS

WITH_IMAGE = {"1-1": (2000, 1000), "1-2": (300, 900)}   # figure 2-1 has no image file on purpose


@pytest.fixture
def root(db, tmp_path):
    make_handbook(tmp_path)
    load_db.load(db, load_db.read_sources(HID, MODEL, tmp_path))
    db.commit()
    folder = tmp_path / "data" / "extracted" / HID / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    for number, size in WITH_IMAGE.items():
        Image.effect_noise(size, 60).convert("RGB").save(folder / f"{number}.png")   # noise: hard to compress
    return tmp_path / "data" / "extracted"


def figure_id(db, number):
    return db.execute("SELECT id FROM figures WHERE figure_number = %s", (number,)).fetchone()[0]


def test_thumbnails_are_small_webp_files_that_keep_the_proportions(db, root):
    result = make_thumbnails.make_thumbnails(db, HID, image_root=root)
    assert result["made"] == 2
    wide = root / HID / "thumbnails" / "1-1.webp"
    with Image.open(wide) as im:
        assert im.format == "WEBP" and im.size == (480, 240)
    with Image.open(root / HID / "thumbnails" / "1-2.webp") as im:
        assert im.size == (160, 480)
    assert wide.stat().st_size < (root / HID / "figures" / "1-1.png").stat().st_size / 4


def test_missing_image_is_reported_and_second_run_makes_nothing(db, root):
    first = make_thumbnails.make_thumbnails(db, HID, image_root=root)
    assert first["missing"] == [figure_id(db, "2-1")]
    second = make_thumbnails.make_thumbnails(db, HID, image_root=root)
    assert second["made"] == 0 and second["skipped"] == 2


def search(pg_test_dsn, root, monkeypatch, vector):
    index = retrieval.load_index_from(pg_test_dsn, image_root=root)
    monkeypatch.setattr(retrieval, "load_index", lambda: index)
    return retrieval.retrieve("anything", k=3, index=index, query_vector=vector)["results"]


def test_results_give_the_thumbnail_and_keep_the_full_image(db, pg_test_dsn, root, monkeypatch):
    make_thumbnails.make_thumbnails(db, HID, image_root=root)
    db.commit()
    by_number = {r["figure_id"]: r for r in search(pg_test_dsn, root, monkeypatch, FIGURE_VECTORS[0])}
    first = by_number["1-1"]
    assert first["thumbnail_url"] == f"/figures/{first['id']}/thumbnail"
    assert first["image_url"] == f"/figures/{first['id']}/image"      # full size still on request
    if "2-1" in by_number:
        assert by_number["2-1"]["thumbnail_url"] is None               # no thumbnail: no URL


def test_thumbnail_route(db, pg_test_dsn, root, monkeypatch):
    make_thumbnails.make_thumbnails(db, HID, image_root=root)
    db.commit()
    first = search(pg_test_dsn, root, monkeypatch, FIGURE_VECTORS[0])[0]
    client = TestClient(app_module.app)
    r = client.get(first["thumbnail_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    for bad in ["999999", "1-1", "..%2F..%2FREADME.md"]:
        assert client.get(f"/figures/{bad}/thumbnail").status_code == 404
