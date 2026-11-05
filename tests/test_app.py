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


def test_search_answerable_question(questions, real_index, monkeypatch):
    # Q003 was written for 15B only (docs/EVALUATION.md 3.3): search 15B only, expected value unchanged.
    from backend import app as app_module
    real = app_module.retrieve
    monkeypatch.setattr(app_module, "retrieve", lambda q, k: real(q, k, handbooks=["FAA-H-8083-15B"]))
    r = client.get("/search", params={"q": questions["Q003"]["question"]})
    body = r.json()
    assert r.status_code == 200 and body["reason"] is None
    assert body["results"][0]["figure_id"] == "3-9"


def test_search_no_answer_is_200_with_reason(questions, real_index):
    r = client.get("/search", params={"q": questions["Q024"]["question"]})
    assert r.status_code == 200
    assert r.json() == {"results": [], "reason": "no_adequate_answer"}


def test_image_exists(real_index):
    fid = client.get("/search", params={"q": "inner ear"}).json()["results"][0]["id"]
    r = client.get(f"/figures/{fid}/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.parametrize("fid", ["99-99", "..%2F..%2FREADME.md", "....//....//README.md"])
def test_image_unknown_or_traversal_is_404(fid, real_index):
    assert client.get(f"/figures/{fid}/image").status_code == 404


def test_page_is_served_when_build_exists(tmp_path, monkeypatch):
    # A tiny fake build, so the test needs neither Node nor a real "npm run build".
    (tmp_path / "index.html").write_text("<!doctype html><div id='root'></div>", encoding="utf-8")
    monkeypatch.setattr("backend.app.DIST", tmp_path)
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"] and "id='root'" in r.text


def test_page_without_build_is_503(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.DIST", tmp_path)  # empty folder: no build
    assert client.get("/").status_code == 503


def test_answer_route_no_answer_does_not_call_the_llm(questions, real_index, monkeypatch):
    from backend import answer as answer_module
    monkeypatch.setattr(answer_module.httpx, "post", lambda *a, **k: pytest.fail("the LLM was called"))
    r = client.get("/answer", params={"q": questions["Q024"]["question"]})
    assert r.status_code == 200
    assert r.json() == {"answer": {"mode": "no_answer", "sentences": [], "fallback_reason": None}, "results": []}


def test_answer_route_validates_q():
    assert client.get("/answer").status_code == 422
    assert client.get("/answer", params={"q": "  "}).status_code == 422
