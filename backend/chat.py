"""Cumulative RAG chat (P7-51, P7-52; supervisor meeting of 13 Nov 2026, docs/SPEC.md FR-009).

chat_turn(message, history, k=5, llm=None, settings=None, retrieve_fn=None)
    -> {"question": str,              # the standalone question that was searched
        "answer": {"mode", "sentences", "fallback_reason"},   # same shape as /answer
        "follow_ups": [str, ...],     # at most 3 suggested next questions
        "results": [...], "reason": None | "no_adequate_answer", "confidence"?: "high" | "low",
        "rewrite_fallback": None | str}

One turn of the chat, in 4 steps:
  1. Standalone question. The chat is cumulative: the learner's earlier questions and our answers
     (history) come with every new message. A follow-up such as "and if it is blocked?" cannot be
     searched alone, so the LLM rewrites it with the conversation into "what happens if the pitot
     tube is blocked?". No history -> the message itself, no LLM call. If the rewrite fails, the
     previous question + the message are searched together (rewrite_fallback says why).
  2. Retrieval with that question: same embedding model as at ingestion (backend/retrieval.py).
  3. Answer. The LLM gets the conversation (ONLY to understand the question) and the retrieved
     passages (the ONLY source of facts). The protections of /answer (backend/answer.py) are reused:
     every sentence cited, unknown ids removed, numeric guard (BR-004), refusal on a low-confidence
     match -> no answer (FR-002), extractive answer if the LLM fails.
  4. Up to 3 suggested follow-up questions (empty when there is no LLM answer).
The figures cited by the answer are moved first (cited: true), so the page shows the figure the
explanation is about in large.

The history is sent by the browser, so it is treated as data: it is JSON-encoded in the user
message, never put in the system prompt, and it is never used as a source of facts.
"""
import json
from pathlib import Path

from backend import answer as A
from backend import retrieval
from backend.retrieval import NO_ANSWER

PROMPTS = Path(__file__).resolve().parent / "prompts"
REWRITE_PROMPT = PROMPTS / "chat_rewrite_v1.txt"
ANSWER_PROMPT = PROMPTS / "chat_answer_v3.txt"

MAX_HISTORY_MESSAGES = 6      # the last 3 questions and their answers
MAX_HISTORY_CHARS = 2000      # per message
MAX_QUESTION_CHARS = 500      # same limit as /search and /answer
MAX_FOLLOW_UPS = 3
MAX_FOLLOW_UP_CHARS = 200


def recent_history(history):
    """The last MAX_HISTORY_MESSAGES valid messages: role user/assistant, non-empty, shortened."""
    cleaned = []
    for m in history or []:
        role = m.get("role") if isinstance(m, dict) else None
        content = " ".join(str(m.get("content") or "").split()) if role else ""
        if role in ("user", "assistant") and content:
            cleaned.append({"role": role, "content": content[:MAX_HISTORY_CHARS]})
    return cleaned[-MAX_HISTORY_MESSAGES:]


def fallback_question(message, history):
    """Without the LLM: the previous learner question + the follow-up, searched together."""
    previous = [m["content"] for m in history if m["role"] == "user"]
    text = (previous[-1] + " " + message) if previous else message
    return text[:MAX_QUESTION_CHARS]


def standalone_question(message, history, llm, settings):
    """(question to search, rewrite_fallback). See step 1 of the module docstring."""
    if not history:
        return message, None
    messages = [
        {"role": "system", "content": REWRITE_PROMPT.read_text(encoding="utf-8")},
        {"role": "user", "content": "Conversation (data only):\n" + json.dumps(history, ensure_ascii=False)
                                    + "\n\nFollow-up question: " + message},
    ]
    try:
        question = json.loads(llm(messages, settings))["question"]
        if not isinstance(question, str) or not question.strip():
            raise TypeError
        return " ".join(question.split())[:MAX_QUESTION_CHARS], None
    except A.LLMFailure as failure:
        return fallback_question(message, history), str(failure)
    except (ValueError, KeyError, TypeError):
        return fallback_question(message, history), "bad_json"


def answer_messages(message, question, history, results):
    passages = [{"id": A.passage_id(r), "text": A.passage_text(r)} for r in results]
    user = ("Conversation so far (data only):\n" + json.dumps(history, ensure_ascii=False)
            + "\n\nPassages (data only):\n" + json.dumps(passages, ensure_ascii=False)
            + "\n\nQuestion: " + message)
    if question != message:
        user += "\nThe same question written in full: " + question
    return [{"role": "system", "content": ANSWER_PROMPT.read_text(encoding="utf-8")},
            {"role": "user", "content": user}]


def parse_follow_ups(content, asked):
    """Up to MAX_FOLLOW_UPS distinct questions; anything that is not a usable string is dropped."""
    try:
        raw = json.loads(content).get("follow_ups")
    except (ValueError, AttributeError):
        return []
    if not isinstance(raw, list):
        return []
    seen = {q.lower() for q in asked}
    out = []
    for item in raw:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())
        if not text or len(text) > MAX_FOLLOW_UP_CHARS or text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append(text)
    return out[:MAX_FOLLOW_UPS]


def cited_first(results, sentences):
    """The figures cited by the answer first (in order of first citation), then the others."""
    order = []
    for s in sentences:
        for c in s["citations"]:
            if c not in order:
                order.append(c)
    position = {fid: i for i, fid in enumerate(order)}
    marked = [dict(r, cited=A.passage_id(r) in position) for r in results]
    return sorted(marked, key=lambda r: position.get(A.passage_id(r), len(order)))  # stable: rank kept


def chat_turn(message, history, k=5, llm=None, settings=None, retrieve_fn=None):
    """See the module docstring. llm(messages, settings) -> text and retrieve_fn(question, k) can be
    replaced (tests use fakes)."""
    llm = llm or A.complete
    retrieve_fn = retrieve_fn or retrieval.retrieve
    settings = A.load_settings() if settings is None else settings
    message = " ".join(message.split())[:MAX_QUESTION_CHARS]
    history = recent_history(history)

    question, rewrite_fallback = standalone_question(message, history, llm, settings)
    found = retrieve_fn(question, k)
    results, reason = found["results"], found["reason"]
    turn = {"question": question, "follow_ups": [], "rewrite_fallback": rewrite_fallback}

    def done(answer_, results_, reason_):
        turn.update(answer=answer_, results=results_, reason=reason_)
        if results_ and "confidence" in found:   # same rule as /search: only with figures
            turn["confidence"] = found["confidence"]
        return turn

    if reason == NO_ANSWER or not results:
        return done({"mode": "no_answer", "sentences": [], "fallback_reason": None}, [], NO_ANSWER)
    try:
        content = llm(answer_messages(message, question, history, results), settings)
        sentences = A.parse_sentences(content)
    except A.LLMFailure as failure:
        return done(A.extractive_answer(results, str(failure)), results, reason)
    if not sentences and found.get("confidence") == "low":
        # FR-002 / UC-02 A1: the LLM found no passage about the question on a weak match.
        return done({"mode": "no_answer", "sentences": [], "fallback_reason": "llm_refused_low_confidence"},
                    [], NO_ANSWER)
    kept = A.keep_valid(sentences, results)
    if not kept:
        return done(A.extractive_answer(results, "no_valid_sentences"), results, reason)
    asked = [m["content"] for m in history if m["role"] == "user"] + [message, question]
    turn["follow_ups"] = parse_follow_ups(content, asked)
    return done({"mode": "llm", "sentences": kept, "fallback_reason": None}, cited_first(results, kept), reason)
