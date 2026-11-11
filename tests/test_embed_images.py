"""Tests for ingestion/embed_images.py and the image search in the database (P7-30), written from
brief section 4 ("Joint retrieval over text and images") and SPEC BR-001 (unknown licence = never
searchable).

A made-up handbook in a temporary database (tests/test_load_db.py) with small PNG figures, and a
FAKE image model (no CLIP download): it gives each image a vector that depends on its width only.
Skipped if PostgreSQL is not running.   Run:   python -m pytest -q tests/test_embed_images.py
"""
import numpy as np
import pytest
from PIL import Image

import embed_images
import load_db
from backend import retrieval
from backend.retrieval import load_index_from
from test_load_db import HID, MODEL, make_handbook

WIDTHS = {"1-1": 100, "1-2": 200}     # figure 2-1 has no image file on purpose


class FakeImageModel:
    """Vector of 512 zeros with a 1 at position (width of the image) // 100."""
    def encode(self, images, normalize_embeddings=True):
        out = np.zeros((len(images), 512), dtype=np.float32)
        for row, img in enumerate(images):
            out[row, img.size[0] // 100] = 1.0
        return out


def one_hot(position):
    v = np.zeros(512, dtype=np.float32)
    v[position] = 1.0
    return v


def load(db, tmp_path, licence="Public domain"):
    make_handbook(tmp_path, licence=licence)
    load_db.load(db, load_db.read_sources(HID, MODEL, tmp_path))
    db.commit()
    folder = tmp_path / "data" / "extracted" / HID / "figures"
    folder.mkdir(parents=True, exist_ok=True)
    for number, width in WIDTHS.items():
        Image.new("L", (width, 50), 128).save(folder / f"{number}.png")   # greyscale: must become RGB
    return tmp_path / "data" / "extracted"


def figure_id(db, number):
    return db.execute("SELECT id FROM figures WHERE figure_number = %s", (number,)).fetchone()[0]


def test_every_figure_with_an_image_gets_a_512_vector_and_the_missing_one_is_reported(db, tmp_path):
    root = load(db, tmp_path)
    result = embed_images.embed_images(db, FakeImageModel(), image_root=root)
    assert result == {"embedded": 2, "missing": [figure_id(db, "2-1")]}
    rows = db.execute("SELECT model, vector_dims(embedding) FROM figure_image_embeddings").fetchall()
    assert rows == [(embed_images.IMAGE_MODEL_NAME, 512)] * 2


def test_second_run_embeds_nothing_new_but_all_redoes_everything(db, tmp_path):
    root = load(db, tmp_path)
    embed_images.embed_images(db, FakeImageModel(), image_root=root)
    assert embed_images.embed_images(db, FakeImageModel(), image_root=root)["embedded"] == 0
    assert embed_images.embed_images(db, FakeImageModel(), image_root=root, redo_all=True)["embedded"] == 2


def test_image_search_finds_the_figure_whose_picture_matches(db, pg_test_dsn, tmp_path):
    root = load(db, tmp_path)
    embed_images.embed_images(db, FakeImageModel(), image_root=root)
    ranked = retrieval.rank_image(load_index_from(pg_test_dsn), one_hot(2), k=2)   # width 200 -> figure 1-2
    assert ranked[0] == (figure_id(db, "1-2"), pytest.approx(1.0))


def test_image_of_a_handbook_with_unknown_licence_is_never_ranked(db, pg_test_dsn, tmp_path):
    root = load(db, tmp_path, licence="unknown")
    embed_images.embed_images(db, FakeImageModel(), image_root=root)
    with pytest.raises(RuntimeError, match="no image embedding"):
        retrieval.rank_image(load_index_from(pg_test_dsn), one_hot(2), k=2)


def test_reloading_the_handbook_removes_its_old_image_vectors(db, tmp_path):
    root = load(db, tmp_path)
    embed_images.embed_images(db, FakeImageModel(), image_root=root)
    db.execute("DELETE FROM documents WHERE id = %s", (HID,))
    assert db.execute("SELECT count(*) FROM figure_image_embeddings").fetchone()[0] == 0
