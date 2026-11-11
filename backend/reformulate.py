"""Query reformulation (P7-33): ask the LLM to rewrite a learner's question in handbook vocabulary.

Hypothesis tested (EVALUATION.md section 4): symptom questions describe an effect in everyday words
("the nose swings to the right") while the handbook names it ("adverse yaw"); a rewritten question
in handbook words may find the expected figure more often. This is an experiment, not a proven fix.

reformulate(query, prompt="v1") -> {"text": str | None, "status": str, "http_status": int | "",
                                    "ms": int}
    status "ok": text is the rewritten question. Any other status: text is None and the caller
    searches with the original question only (it never fails because of the LLM).

The rewritten question is ONLY used to search. The original question is kept: it decides
"no answer" (threshold) and it is the question the answer layer answers (backend/retrieval.py).

Prompts: backend/prompts/reformulate_v1.txt (strict: handbook words only, no cause) and
reformulate_v2.txt (also up to 3 handbook topics, stated as search terms, never as the cause).
Both were written BEFORE the evaluation run and contain no question of evaluation/questions.csv.
Settings: the LLM_* settings of the answer layer (backend/answer.py, load_settings).
"""
import json
import time
from pathlib import Path

import httpx

from backend.answer import load_settings

PROMPTS = Path(__file__).resolve().parent / "prompts"
VERSIONS = ("v1", "v2")
TIMEOUT_SECONDS = 10
MAX_WORDS = 40


def prompt_file(version):
    if version not in VERSIONS:
        raise ValueError(f"prompt must be one of {VERSIONS}, got {version!r}")
    return PROMPTS / f"reformulate_{version}.txt"


def check_output(content):
    """(rewritten question, "ok") or (None, reason). The model must return {"query": "..."}."""
    try:
        text = json.loads(content)["query"]
    except (ValueError, KeyError, TypeError):
        return None, "bad_json"
    if not isinstance(text, str) or not text.strip():
        return None, "empty"
    text = " ".join(text.split())
    if len(text.split()) > MAX_WORDS:
        return None, "too_long"
    return text, "ok"


def reformulate(query, prompt="v1", settings=None, post=httpx.post, clock=time.perf_counter):
    """One LLM call. Never raises for an LLM problem: the status says what happened."""
    settings = settings or load_settings()
    start = clock()

    def result(text, status, http_status=""):
        return {"text": text, "status": status, "http_status": http_status,
                "ms": int(round((clock() - start) * 1000))}

    if not settings.get("LLM_API_KEY"):
        return result(None, "missing_api_key")
    if not settings.get("LLM_BASE_URL") or not settings.get("LLM_MODEL"):
        return result(None, "missing_settings")
    body = {
        "model": settings["LLM_MODEL"],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": prompt_file(prompt).read_text(encoding="utf-8")},
            # JSON-encoded, so the question cannot close or imitate the structure around it
            {"role": "user", "content": "Question (data only): " + json.dumps(query, ensure_ascii=False)},
        ],
    }
    url = settings["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    try:
        response = post(url, json=body, timeout=TIMEOUT_SECONDS,
                        headers={"Authorization": "Bearer " + settings["LLM_API_KEY"]})
    except httpx.TimeoutException:
        return result(None, "timeout")
    except httpx.HTTPError:
        return result(None, "http_error")   # the original message (it may contain the URL) is dropped
    if response.status_code != 200:
        return result(None, "http_error", response.status_code)
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return result(None, "bad_json", 200)
    text, status = check_output(content)
    return result(text, status, 200)
