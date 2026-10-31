"""Status-code tests for backend/app.py.   Run from the repository root:   python -m pytest -q tests/test_app.py"""
import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_search_missing_q_is_422():
    assert client.get("/search").status_code == 422


@pytest.mark.parametrize("q", ["", "   "])
def test_search_empty_or_blank_q_is_422(q):
    assert client.get("/search", params={"q": q}).status_code == 422


def test_search_bad_k_is_422(real_index):
    assert client.get("/search", params={"q": "inner ear", "k": 0}).status_code == 422


def test_search_answerable_question(questions, real_index):
    r = client.get("/search", params={"q": questions["Q003"]["question"]})
    body = r.json()
    assert r.status_code == 200 and body["reason"] is None
    assert body["results"][0]["figure_id"] == "3-9"


def test_search_no_answer_is_200_with_reason(questions, real_index):
    r = client.get("/search", params={"q": questions["Q024"]["question"]})
    assert r.status_code == 200
    assert r.json() == {"results": [], "reason": "no_adequate_answer"}


def test_image_exists(real_index):
    r = client.get("/figures/3-9/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("fid", ["99-99", "..%2F..%2FREADME.md", "....//....//README.md"])
def test_image_unknown_or_traversal_is_404(fid, real_index):
    assert client.get(f"/figures/{fid}/image").status_code == 404


def test_page_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "No adequate answer found in the handbook" in r.text
