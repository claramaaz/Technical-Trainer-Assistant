"""Re-embedding and re-indexing (P7-32; FR-008, UC-10, UC-04) with fake models and a fake connection."""
from contextlib import contextmanager

import numpy as np
import pytest
from fastapi.testclient import TestClient

import reindex
from backend import auth, embedding, ingest_jobs
from backend.app import app

client = TestClient(app)
GEMINI = "gemini-embedding-001"


class FakeConn:
    def __init__(self, rows):
        self.rows, self.writes, self.in_transaction = rows, [], False

    def execute(self, sql, params=()):
        if sql.lstrip().startswith("SELECT"):
            return type("R", (), {"fetchall": lambda _s: self.rows})()
        assert self.in_transaction, "every write must be inside the single transaction"
        self.writes.append((sql.split()[0], params))

    @contextmanager
    def transaction(self):
        self.in_transaction = True
        yield
        self.in_transaction = False


def local(texts):
    return np.ones((len(texts), 384))


def test_both_models_are_rebuilt_from_the_stored_text():
    conn, seen = FakeConn([(1, "Figure 1-1. Corrected caption"), (2, "Figure 1-2. B")]), []
    api = lambda model, texts, kind: seen.append((model, texts, kind)) or np.ones((len(texts), 768))
    assert reindex.rebuild(conn, conn.rows, model=GEMINI, local=local, api=api) == 2
    assert seen == [(GEMINI, ["Figure 1-1. Corrected caption", "Figure 1-2. B"], "document")]
    assert [w[0] for w in conn.writes] == ["UPDATE", "INSERT", "UPDATE", "INSERT"]


def test_api_failure_writes_nothing_and_keeps_the_old_index():
    conn = FakeConn([(1, "a"), (2, "b")])

    def no_quota(*a):
        raise embedding.EmbeddingError("embedding API failed: HTTP 429")
    with pytest.raises(embedding.EmbeddingError):
        reindex.rebuild(conn, conn.rows, model=GEMINI, local=local, api=no_quota)
    assert conn.writes == []


def test_bge_only_needs_no_api():
    conn = FakeConn([(1, "a")])
    reindex.rebuild(conn, conn.rows, model=embedding.LOCAL_MODEL, local=local,
                    api=lambda *a: pytest.fail("API called"))
    assert [w[0] for w in conn.writes] == ["UPDATE"]


def test_unknown_figure_is_zero():
    assert reindex.reembed_figure(FakeConn([]), 999, local=local) == 0


# ---- routes ----

@pytest.fixture
def as_admin():
    app.dependency_overrides[auth.current_user] = lambda: {"id": 7, "email": "admin@test", "role": "admin"}
    yield
    app.dependency_overrides[auth.current_user] = lambda: {"id": 0, "email": "test@learner", "role": "learner"}


def test_learner_cannot_reindex_or_reembed():
    assert client.post("/admin/reindex", json={}).status_code == 403
    assert client.post("/admin/figures/5/reembed").status_code == 403


def test_reindex_starts_a_job_with_the_reindex_step(as_admin, monkeypatch):
    started = []
    monkeypatch.setattr(ingest_jobs, "create_reindex_job", lambda hid, uid: (hid, uid) == ("FAA-H-8083-15B", 7) and 12)
    monkeypatch.setattr(ingest_jobs, "start", lambda job_id, todo=None: started.append((job_id, todo)))
    r = client.post("/admin/reindex", json={"handbook_id": "FAA-H-8083-15B"})
    assert r.status_code == 202 and r.json() == {"job_id": 12, "status": "queued"}
    (job_id, todo), = started
    assert job_id == 12 and todo[0][0] == "re-index" and todo[0][1][1:] == ["ingestion/reindex.py", "FAA-H-8083-15B"]


def test_reindex_refusal_keeps_its_status(as_admin, monkeypatch):
    def busy(*a):
        raise ingest_jobs.UploadError("another job is running", 409)
    monkeypatch.setattr(ingest_jobs, "create_reindex_job", busy)
    assert client.post("/admin/reindex", json={}).status_code == 409


@pytest.mark.parametrize("result, status", [(1, 200), (0, 404)])
def test_reembed_route(as_admin, monkeypatch, result, status):
    monkeypatch.setattr(reindex, "reembed_figure", lambda conn, fid: result)

    @contextmanager
    def fake_connect(dsn):
        yield None
    from backend import retrieval
    monkeypatch.setattr(retrieval, "connect", fake_connect)
    monkeypatch.setattr(retrieval, "connection_string", lambda: "fake")
    assert client.post("/admin/figures/5/reembed").status_code == status
