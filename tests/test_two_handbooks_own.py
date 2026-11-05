"""Two handbooks that both have a figure "3-1": each result must carry ITS OWN handbook and ITS OWN image.

Bug found while adding FAA-H-8083-25C: retrieve() put the handbook of the first database row on every
result, and the image route looked a figure up by its printed number, so the first match won.
No database and no model: a fake in-memory index with two handbooks (see tests/fake_index.py).
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import retrieval
from backend.app import app
from backend.retrieval import retrieve
from fake_index import make_fake

QUERY = np.array([1.0, 0.0])
PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def two_handbooks(tmp_path):
    """Row 0 = figure 3-1 of handbook A, row 1 = figure 3-1 of handbook B (better score), row 2 = other."""
    docs = []
    for handbook_id, title, page in [("HB-A", "Handbook A", "3-3"), ("HB-B", "Handbook B", "3-7")]:
        image = tmp_path / f"{handbook_id}.png"
        image.write_bytes(PNG + handbook_id.encode())
        docs.append({
            "figure_number": "3-1", "caption": f"Figure 3-1. From {title}", "image_path": image,
            "passage": f"Text of {title}.", "printed_page": page,
            "handbook_id": handbook_id, "handbook": title,
        })
    vectors = np.array([[0.80, 0.6], [0.90, 0.43589]])
    return make_fake(docs, vectors)


def test_each_result_has_its_own_handbook(two_handbooks):
    results = retrieve("q", k=2, index=two_handbooks, query_vector=QUERY)["results"]
    assert [(r["handbook_id"], r["handbook"], r["printed_page"]) for r in results] == [
        ("HB-B", "Handbook B", "3-7"), ("HB-A", "Handbook A", "3-3")]


def test_results_carry_the_database_id_and_the_printed_number(two_handbooks):
    results = retrieve("q", k=2, index=two_handbooks, query_vector=QUERY)["results"]
    assert [r["id"] for r in results] == [1, 0]
    assert [r["figure_id"] for r in results] == ["3-1", "3-1"]
    assert [r["image_url"] for r in results] == ["/figures/1/image", "/figures/0/image"]


def test_image_path_is_looked_up_by_database_id_only(two_handbooks, monkeypatch):
    monkeypatch.setattr(retrieval, "load_index", lambda: two_handbooks)
    assert retrieval.image_path_for(0).name == "HB-A.png"
    assert retrieval.image_path_for(1).name == "HB-B.png"
    # the printed number is no longer an id, and neither is anything that is not a known database id
    for bad in ["3-1", "99", 99, "../../etc/passwd", "", None, "1.0", "01x"]:
        assert retrieval.image_path_for(bad) is None


def test_image_route_serves_the_right_image_for_each_handbook(two_handbooks, monkeypatch):
    monkeypatch.setattr(retrieval, "load_index", lambda: two_handbooks)
    client = TestClient(app)
    assert client.get("/figures/0/image").content.endswith(b"HB-A")
    assert client.get("/figures/1/image").content.endswith(b"HB-B")
    assert client.get("/figures/3-1/image").status_code == 404


def test_handbooks_filter_keeps_only_the_chosen_handbook(two_handbooks):
    only_a = retrieve("q", k=5, index=two_handbooks, query_vector=QUERY, handbooks=["HB-A"])["results"]
    assert [(r["id"], r["handbook_id"]) for r in only_a] == [(0, "HB-A")]
    both = retrieve("q", k=5, index=two_handbooks, query_vector=QUERY)["results"]
    assert len(both) == 2


def test_handbooks_filter_on_the_real_database(real_index):
    for hb in {d["handbook_id"] for d in real_index.documents.values()}:
        out = retrieve("four forces acting on an airplane", k=5, handbooks=[hb])
        assert {r["handbook_id"] for r in out["results"]} <= {hb}
