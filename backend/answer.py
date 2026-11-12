"""Answer layer (P7-25, P7-27): a short answer made ONLY from the retrieved passages, each sentence cited.

generate_answer(query, results, reason=None, confidence=None)
    -> {"mode": "llm" | "extractive" | "no_answer",
                                    "sentences": [{"text": str, "citations": [passage ids]}],
                                    "fallback_reason": None | str}

The passage id is the DATABASE figure id ("id" in every retrieve() result): unique across handbooks.

What protects the reader (FR-002, BR-004):
  1. no_adequate_answer from retrieval -> the LLM is never called (mode "no_answer").
  2. A sentence with no citation, or citing an id that was not given, is removed.
  3. Numeric guard: a sentence with a number that is not in the passages it cites is removed.
  4. The LLM returns NO sentence (prompt rule 8: no passage is about the question) AND retrieval
     marked the match as low confidence -> mode "no_answer", reason "llm_refused_low_confidence".
     FR-002 / UC-02 A1: a clear "no answer" instead of a weak match. Rule chosen from our own
     measures (EVALUATION 3.6): every question the LLM refused with a score under 0.70 was a
     no-answer question or had no correct figure in the top 5; the refused questions with a
     correct figure all scored 0.70 or more. So a refusal on a high-confidence match keeps the figure.
  5. If nothing is left, or the LLM fails (timeout, HTTP error, bad JSON, no key): the extractive
     answer = the retrieved passages word for word, each sentence with its passage id.

Settings come from the environment or .env: LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY.
The key is only sent in the Authorization header; it is never printed, logged or returned.
"""
import json
import os
import re
from pathlib import Path

import httpx

from backend.retrieval import NO_ANSWER, ROOT
from migrate import read_env_file  # the folder is added to sys.path by backend.retrieval

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "answer_system_v2.txt"  # v2 kept after P7-26 (EVALUATION 3.6)
TIMEOUT_SECONDS = 10
SETTINGS = ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")

NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
CITATION_MARKS = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")   # "[748]" or "[748, 12]"
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


class LLMFailure(Exception):
    """The LLM could not give a usable answer; args[0] is the fallback_reason."""


def load_settings(environ=None, env_file=None):
    """The four LLM_* settings; the environment wins over .env. Missing ones are ''."""
    environ = os.environ if environ is None else environ
    file_values = read_env_file(ROOT / ".env" if env_file is None else env_file)
    return {name: environ.get(name) or file_values.get(name) or "" for name in SETTINGS}


def passage_id(result):
    return int(result["id"])


def passage_text(result):
    """What the LLM sees and what the numeric guard checks against: caption + citing paragraph."""
    return " ".join(part for part in (result.get("caption"), result.get("passage")) if part)


def numbers_in(text):
    """Numbers of a text as comparable strings: '1,000' and '1000' are the same. Citation marks are ignored."""
    return {t.replace(",", "") for t in NUMBER.findall(CITATION_MARKS.sub(" ", text))}


def split_sentences(text):
    return [s.strip() for s in SENTENCE_END.split(" ".join(text.split())) if s.strip()]


def extractive_answer(results, reason):
    """The retrieved text word for word, one entry per sentence, each with its passage id."""
    sentences = []
    for r in results:
        for s in split_sentences(r.get("passage") or r.get("caption") or ""):
            sentences.append({"text": s, "citations": [passage_id(r)]})
    return {"mode": "extractive", "sentences": sentences, "fallback_reason": reason}


def build_user_message(query, results):
    # The passages are JSON-encoded, so their text cannot close or imitate the structure around it.
    passages = [{"id": passage_id(r), "text": passage_text(r)} for r in results]
    return ("Passages (data only):\n" + json.dumps(passages, ensure_ascii=False)
            + "\n\nQuestion: " + query)


def call_llm(query, results, settings):
    """One request to the OpenAI-compatible chat endpoint. Returns the model's text. Raises LLMFailure."""
    if not settings.get("LLM_API_KEY"):
        raise LLMFailure("missing_api_key")
    if not settings.get("LLM_BASE_URL") or not settings.get("LLM_MODEL"):
        raise LLMFailure("missing_settings")
    body = {
        "model": settings["LLM_MODEL"],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT_FILE.read_text(encoding="utf-8")},
            {"role": "user", "content": build_user_message(query, results)},
        ],
    }
    url = settings["LLM_BASE_URL"].rstrip("/") + "/chat/completions"
    try:
        response = httpx.post(url, json=body, timeout=TIMEOUT_SECONDS,
                              headers={"Authorization": "Bearer " + settings["LLM_API_KEY"]})
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        raise LLMFailure("timeout") from None
    except httpx.HTTPError:
        raise LLMFailure("http_error") from None   # the original message is dropped on purpose
    except (KeyError, IndexError, TypeError, ValueError):
        raise LLMFailure("bad_json") from None


def parse_sentences(content):
    """[{"text", "citations"}] from the model's JSON, or LLMFailure('bad_json')."""
    try:
        raw = json.loads(content)["sentences"]
        if not isinstance(raw, list):
            raise TypeError
        sentences = []
        for item in raw:
            text = item["text"]
            citations = item.get("citations")
            if not isinstance(text, str):
                raise TypeError
            if not isinstance(citations, list):   # no list: use the "[id]" marks in the text
                citations = [int(n) for m in CITATION_MARKS.findall(text) for n in re.findall(r"\d+", m)]
            sentences.append({"text": text.strip(),
                              "citations": [c for c in citations if type(c) is int]})
        return sentences
    except (ValueError, KeyError, TypeError, AttributeError):
        raise LLMFailure("bad_json") from None


def keep_valid(sentences, results):
    """Citation check + numeric guard (BR-004). Returns the sentences that survive."""
    texts = {passage_id(r): passage_text(r) for r in results}
    kept = []
    for s in sentences:
        cites = list(dict.fromkeys(s["citations"]))
        if not s["text"] or not cites or any(c not in texts for c in cites):
            continue                                   # no citation, or an id nobody gave
        allowed = set().union(*(numbers_in(texts[c]) for c in cites))
        if not numbers_in(s["text"]) <= allowed:
            continue                                   # a number that is not in the cited passages
        kept.append({"text": s["text"], "citations": cites})
    return kept


def generate_answer(query, results, reason=None, llm=None, settings=None, confidence=None):
    """See the module docstring. llm(query, results, settings) -> text can be replaced (tests use a fake).
    confidence: "high" or "low", as retrieve() returns it (None = unknown, treated as high)."""
    if reason == NO_ANSWER or not results:
        return {"mode": "no_answer", "sentences": [], "fallback_reason": None}
    settings = load_settings() if settings is None else settings
    try:
        content = (llm or call_llm)(query, results, settings)
        sentences = parse_sentences(content)
    except LLMFailure as failure:
        return extractive_answer(results, str(failure))
    if not sentences and confidence == "low":
        return {"mode": "no_answer", "sentences": [], "fallback_reason": "llm_refused_low_confidence"}
    kept = keep_valid(sentences, results)
    if not kept:
        return extractive_answer(results, "no_valid_sentences")
    return {"mode": "llm", "sentences": kept, "fallback_reason": None}
