"""Text embedding models (P7-57; supervisor meeting of 13 Nov 2026).

The same model must embed the documents at ingestion and the question at search time (same model,
same dimension), otherwise the two vectors cannot be compared. Which model is used is chosen with
EMBEDDING_MODEL (environment or .env); the default is the local model we started with.

    BAAI/bge-small-en-v1.5   local (sentence-transformers), 384 dimensions, stored in figures.embedding
                             and chunks.embedding (001_init.sql). No key, no network.
    gemini-embedding-001     Google Gemini API, 768 dimensions, key GEMINI_API_KEY.
    text-embedding-3-small   OpenAI API, 768 dimensions (the API shortens it), key OPENAI_API_KEY.

The two API models are stored in figure_text_embeddings / chunk_text_embeddings (010), one row per
(item, model), so several models can be compared on the same 50 questions without reloading.

API models get a task type where the API has one: a document is embedded as a document and a
question as a query (Gemini RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY), which is how Google asks retrieval
to be done. Vectors are normalised to length 1. Keys are only sent in a header, never printed.
"""
import os
import time
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parent.parent

LOCAL_MODEL = "BAAI/bge-small-en-v1.5"
API_DIMENSIONS = 768        # vector(768) in 010_text_embeddings.sql
MODELS = {
    LOCAL_MODEL: {"provider": "local", "dimensions": 384},
    "gemini-embedding-001": {"provider": "gemini", "dimensions": API_DIMENSIONS, "key": "GEMINI_API_KEY",
                             "batch": 100},
    "text-embedding-3-small": {"provider": "openai", "dimensions": API_DIMENSIONS, "key": "OPENAI_API_KEY",
                               "batch": 100},
}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
OPENAI_URL = "https://api.openai.com/v1/embeddings"
TIMEOUT_SECONDS = 60
RETRIES = 5                 # on HTTP 429 (rate limit) and 5xx, waiting 2, 4, 8, 16, 32 s


class EmbeddingError(Exception):
    """The embedding API could not give vectors; the message never contains the key."""


def _read_env_file(path):
    import sys
    sys.path.insert(0, str(ROOT / "ingestion"))
    from migrate import read_env_file
    return read_env_file(path)


def setting(name, environ=None, env_file=None):
    environ = os.environ if environ is None else environ
    return (environ.get(name) or _read_env_file(env_file or ROOT / ".env").get(name) or "").strip()


def configured_model(environ=None, env_file=None):
    """EMBEDDING_MODEL from the environment, else .env, else the local bge model. Unknown -> ValueError."""
    name = setting("EMBEDDING_MODEL", environ, env_file) or LOCAL_MODEL
    if name not in MODELS:
        raise ValueError(f"EMBEDDING_MODEL must be one of {sorted(MODELS)}, got {name!r}")
    return name


def is_api_model(model):
    return MODELS[model]["provider"] != "local"


def normalise(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if (norms == 0).any():
        raise EmbeddingError("the API returned an empty (zero) vector")
    return vectors / norms


def _post(url, body, headers, post=None, sleep=time.sleep):
    """POST with retries on 429 / 5xx. Returns the JSON body. Raises EmbeddingError."""
    post = post or httpx.post
    for attempt in range(RETRIES + 1):
        try:
            response = post(url, json=body, headers=headers, timeout=TIMEOUT_SECONDS)
        except httpx.TimeoutException:
            error = "timeout"
        except httpx.HTTPError:
            error = "network error"
        else:
            if response.status_code < 400:
                return response.json()
            error = f"HTTP {response.status_code}"
            if response.status_code != 429 and response.status_code < 500:
                break                      # 400, 401, 403...: retrying will not help
        if attempt < RETRIES:
            sleep(2 ** (attempt + 1))
    raise EmbeddingError(f"embedding API failed: {error}")


def _gemini(model, texts, task, key, post=None, sleep=time.sleep):
    body = {"requests": [{"model": f"models/{model}", "content": {"parts": [{"text": t}]},
                          "taskType": task, "outputDimensionality": API_DIMENSIONS} for t in texts]}
    data = _post(GEMINI_URL.format(model=model), body, {"x-goog-api-key": key}, post, sleep)
    try:
        return [e["values"] for e in data["embeddings"]]
    except (KeyError, TypeError):
        raise EmbeddingError("unexpected Gemini response") from None


def _openai(model, texts, key, post=None, sleep=time.sleep):
    body = {"model": model, "input": texts, "dimensions": API_DIMENSIONS}
    data = _post(OPENAI_URL, body, {"Authorization": "Bearer " + key}, post, sleep)
    try:
        return [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]
    except (KeyError, TypeError):
        raise EmbeddingError("unexpected OpenAI response") from None


def embed_api(model, texts, kind, key=None, post=None, sleep=time.sleep):
    """Vectors (n x 768, normalised) for texts with an API model. kind: "document" or "query"."""
    spec = MODELS[model]
    key = key or setting(spec["key"])
    if not key:
        raise EmbeddingError(f"{spec['key']} is not set in .env")
    out = []
    for start in range(0, len(texts), spec["batch"]):
        batch = [t if t.strip() else "(empty)" for t in texts[start:start + spec["batch"]]]
        if spec["provider"] == "gemini":
            task = "RETRIEVAL_DOCUMENT" if kind == "document" else "RETRIEVAL_QUERY"
            vectors = _gemini(model, batch, task, key, post, sleep)
        else:
            vectors = _openai(model, batch, key, post, sleep)
        if len(vectors) != len(batch) or any(len(v) != spec["dimensions"] for v in vectors):
            raise EmbeddingError("the API returned the wrong number or size of vectors")
        out.extend(vectors)
    return normalise(out) if out else np.zeros((0, spec["dimensions"]), dtype=np.float32)
