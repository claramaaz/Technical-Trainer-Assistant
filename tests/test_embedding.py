"""API embedding models (P7-57) with a FAKE HTTP post: no network, no key, no database."""
from contextlib import contextmanager

import numpy as np
import pytest

from backend import embedding, retrieval
from backend.embedding import EmbeddingError, embed_api

GEMINI = "gemini-embedding-001"
OPENAI = "text-embedding-3-small"


class Response:
    def __init__(self, status, body=None):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def vector(i, dims=768):
    v = np.zeros(dims)
    v[i % dims] = 3.0          # length 3: the code must normalise it to 1
    return v.tolist()


class FakePost:
    """Answers like the API; records (url, body, headers). statuses: first answers, e.g. [429]."""
    def __init__(self, provider, statuses=(), dims=768):
        self.provider, self.statuses, self.dims, self.calls = provider, list(statuses), dims, []

    def __call__(self, url, json, headers, timeout):
        self.calls.append((url, json, headers))
        if self.statuses:
            return Response(self.statuses.pop(0))
        if self.provider == "gemini":
            return Response(200, {"embeddings": [{"values": vector(i, self.dims)} for i in range(len(json["requests"]))]})
        n = len(json["input"])   # OpenAI may answer out of order: the index field says where each goes
        return Response(200, {"data": [{"index": i, "embedding": vector(i, self.dims)} for i in reversed(range(n))]})


def no_sleep(_seconds):
    pass


def test_gemini_request_document_and_query_task_types_and_header():
    post = FakePost("gemini")
    docs = embed_api(GEMINI, ["a", "b"], "document", key="k-test", post=post, sleep=no_sleep)
    embed_api(GEMINI, ["q"], "query", key="k-test", post=post, sleep=no_sleep)
    (url, body, headers), (_u, qbody, _h) = post.calls
    assert url.endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert headers == {"x-goog-api-key": "k-test"} and "k-test" not in url
    assert [r["taskType"] for r in body["requests"]] == ["RETRIEVAL_DOCUMENT"] * 2
    assert qbody["requests"][0]["taskType"] == "RETRIEVAL_QUERY"
    assert body["requests"][0]["outputDimensionality"] == 768
    assert docs.shape == (2, 768) and np.allclose(np.linalg.norm(docs, axis=1), 1.0)


def test_openai_request_and_order_by_index():
    post = FakePost("openai")
    out = embed_api(OPENAI, ["a", "b", "c"], "document", key="k-test", post=post, sleep=no_sleep)
    (url, body, headers), = post.calls
    assert url == embedding.OPENAI_URL and body["dimensions"] == 768 and body["input"] == ["a", "b", "c"]
    assert headers == {"Authorization": "Bearer k-test"}
    assert [int(np.argmax(v)) for v in out] == [0, 1, 2]       # put back in input order


def test_texts_are_sent_in_batches_of_100():
    post = FakePost("gemini")
    out = embed_api(GEMINI, [f"t{i}" for i in range(250)], "document", key="k", post=post, sleep=no_sleep)
    assert [len(b["requests"]) for _u, b, _h in post.calls] == [100, 100, 50] and len(out) == 250


def test_rate_limit_is_retried_then_succeeds():
    waits = []
    post = FakePost("gemini", statuses=[429, 503])
    out = embed_api(GEMINI, ["a"], "document", key="k", post=post, sleep=waits.append)
    assert len(post.calls) == 3 and waits == [2, 4] and out.shape == (1, 768)


def test_bad_key_is_not_retried_and_the_key_is_not_in_the_error():
    post = FakePost("openai", statuses=[401])
    with pytest.raises(EmbeddingError) as err:
        embed_api(OPENAI, ["a"], "document", key="secret-key-123", post=post, sleep=no_sleep)
    assert len(post.calls) == 1 and "401" in str(err.value) and "secret-key-123" not in str(err.value)


def test_missing_key_stops_before_any_request(monkeypatch):
    monkeypatch.setattr(embedding, "setting", lambda name, *a: "")
    with pytest.raises(EmbeddingError, match="GEMINI_API_KEY"):
        embed_api(GEMINI, ["a"], "document", post=lambda *a, **k: pytest.fail("request sent"))


def test_wrong_vector_size_is_refused():
    with pytest.raises(EmbeddingError, match="size"):
        embed_api(GEMINI, ["a"], "document", key="k", post=FakePost("gemini", dims=3072), sleep=no_sleep)


def test_configured_model_default_choice_and_unknown(monkeypatch, tmp_path):
    empty_env = tmp_path / ".env"
    empty_env.write_text("", encoding="utf-8")
    assert embedding.configured_model({}, empty_env) == embedding.LOCAL_MODEL
    assert embedding.configured_model({"EMBEDDING_MODEL": GEMINI}, empty_env) == GEMINI
    with pytest.raises(ValueError, match="EMBEDDING_MODEL"):
        embedding.configured_model({"EMBEDDING_MODEL": "gpt-oss-120b"}, empty_env)   # a chat model


# ---- backend/retrieval.py with an API model ----

def test_bge_keeps_its_thresholds_and_sql():
    assert retrieval.thresholds() == (retrieval.THRESHOLD, retrieval.LOW_CONFIDENCE_BELOW)
    sql, params, model = retrieval._text_sql(retrieval.RANK_SQL, retrieval.RANK_SQL_API, {"k": 5})
    assert sql == retrieval.RANK_SQL and params == {"k": 5} and model == embedding.LOCAL_MODEL


def test_api_model_reads_its_own_vectors(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", GEMINI)
    sql, params, model = retrieval._text_sql(retrieval.RANK_SQL, retrieval.RANK_SQL_API, {"k": 5})
    assert sql == retrieval.RANK_SQL_API and params == {"k": 5, "model": GEMINI}
    assert "searchable_figure_text" in sql and "model = %(model)s" in sql


def test_api_model_without_thresholds_stops_with_a_clear_message(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", GEMINI)
    monkeypatch.setattr(retrieval, "MODEL_THRESHOLDS", {GEMINI: None})
    monkeypatch.setattr(embedding, "setting", lambda name, *a: "" if name.startswith("RETRIEVAL_") else GEMINI)
    with pytest.raises(ValueError, match="RETRIEVAL_THRESHOLD"):
        retrieval.thresholds()


def test_api_model_thresholds_from_env_or_from_the_table(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", GEMINI)
    monkeypatch.setenv("RETRIEVAL_THRESHOLD", "0.5")
    monkeypatch.setenv("RETRIEVAL_LOW_CONFIDENCE", "0.6")
    assert retrieval.thresholds() == (0.5, 0.6)
    monkeypatch.delenv("RETRIEVAL_THRESHOLD")
    monkeypatch.delenv("RETRIEVAL_LOW_CONFIDENCE")
    monkeypatch.setattr(embedding, "setting", lambda name, *a: "" if name.startswith("RETRIEVAL_") else GEMINI)
    monkeypatch.setattr(retrieval, "MODEL_THRESHOLDS", {GEMINI: (0.55, 0.62)})
    assert retrieval.thresholds() == (0.55, 0.62)


def test_question_is_embedded_as_a_query_with_the_api_model(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", GEMINI)
    seen = []
    monkeypatch.setattr(embedding, "embed_api", lambda m, texts, kind: seen.append((m, texts, kind)) or np.ones((1, 768)))
    assert retrieval.embed_query("what is a pitot tube").shape == (768,)
    assert seen == [(GEMINI, ["what is a pitot tube"], "query")]


# ---- ingestion/embed_text.py with a fake connection ----

class FakeConn:
    def __init__(self, rows):
        self.rows, self.inserted = rows, []

    def execute(self, sql, params):
        if sql.lstrip().startswith("SELECT"):
            assert params["model"] == GEMINI
            return type("R", (), {"fetchall": lambda _self: self.rows})()
        self.inserted.append(params)

    @contextmanager
    def transaction(self):
        yield


def test_embed_target_embeds_the_stored_text_in_batches():
    import sys
    sys.path.insert(0, str(embedding.ROOT / "ingestion"))
    from embed_text import embed_target
    conn = FakeConn([(i, f"figure {i}") for i in range(1, 6)])
    calls = []
    fake = lambda model, texts, kind: calls.append((model, texts, kind)) or np.ones((len(texts), 768))
    assert embed_target(conn, "figures", GEMINI, embed=fake, batch=2, report=lambda _m: None) == 5
    assert [len(t) for _m, t, _k in calls] == [2, 2, 1] and all(k == "document" for _m, _t, k in calls)
    assert [(fid, model) for fid, model, _v in conn.inserted] == [(i, GEMINI) for i in range(1, 6)]


def test_api_failure_falls_back_to_bge_for_that_search(monkeypatch):
    # The live system keeps answering when Gemini is down or out of quota (P7-57, reliability).
    monkeypatch.setenv("EMBEDDING_MODEL", GEMINI)
    monkeypatch.setattr(retrieval, "MODEL_THRESHOLDS", {GEMINI: (0.64, 0.66)})

    def no_quota(*a):
        raise EmbeddingError("embedding API failed: HTTP 429")
    monkeypatch.setattr(embedding, "embed_api", no_quota)
    monkeypatch.setattr(retrieval, "_model", lambda: type("M", (), {"encode": lambda self, t, **k: np.ones((1, 384))})())
    seen = []

    def fake_rank_query(index, query, vector, k, handbooks, mode, reformulated):
        seen.append((retrieval.text_model(), len(vector), retrieval.thresholds()))
        return [], None
    monkeypatch.setattr(retrieval, "rank_query", fake_rank_query)
    out = retrieval.retrieve("what is a pitot tube", index=object(), mode="text")
    assert seen == [(embedding.LOCAL_MODEL, 384, (retrieval.THRESHOLD, retrieval.LOW_CONFIDENCE_BELOW))]
    assert out["embedding_fallback"] == embedding.LOCAL_MODEL and out["reason"] == retrieval.NO_ANSWER
    assert retrieval.text_model() == GEMINI       # only that search used bge


def test_question_vectors_are_cached_on_disk(monkeypatch, tmp_path):
    monkeypatch.setenv("EMBEDDING_MODEL", GEMINI)
    monkeypatch.setattr(retrieval, "QUERY_CACHE", tmp_path / "cache.jsonl")
    calls = []
    monkeypatch.setattr(embedding, "embed_api", lambda m, t, kind: calls.append(t) or np.full((1, 768), 0.5))
    first = retrieval.embed_query("q1")
    monkeypatch.setattr(retrieval, "_query_cache", None)      # a new process reads the file again
    second = retrieval.embed_query("q1")
    assert calls == [["q1"]] and np.allclose(first, second)

