"""Tests for the start-up warm-up (NFR-001): the first question after a (re)start must not wait for the
embedding model. Found with the query log (P7-28): 30,573 ms for the first question, 517 ms after.

No database and no model: load_index and embed_query are replaced by fakes.
Run:   python -m pytest -q tests/test_warm_up.py
"""
from fastapi.testclient import TestClient

from backend import app as app_module
from backend import retrieval


def test_warm_up_loads_the_index_and_the_model(monkeypatch):
    calls = []
    monkeypatch.setattr(retrieval, "load_index", lambda: calls.append("index"))
    monkeypatch.setattr(retrieval, "embed_query", lambda q: calls.append("model"))
    assert app_module.warm_up() is True
    assert calls == ["index", "model"]


def test_server_still_starts_when_the_database_is_down(monkeypatch):
    def down():
        raise OSError("connection refused")
    monkeypatch.setattr(retrieval, "load_index", down)
    monkeypatch.setattr(retrieval, "embed_query", lambda q: None)
    assert app_module.warm_up() is False          # no exception
    with TestClient(app_module.app) as client:    # start-up runs warm_up
        assert client.get("/health").status_code == 200


def test_warm_up_runs_once_at_start_up_not_on_every_request(monkeypatch):
    calls = []
    monkeypatch.setattr(app_module, "warm_up", lambda: calls.append(1))
    with TestClient(app_module.app) as client:
        client.get("/health")
        client.get("/health")
    assert calls == [1]
