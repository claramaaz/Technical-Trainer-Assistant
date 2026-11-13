"""Query log (P7-28; FR-007, UC-02 postconditions): one row in query_log per question asked.

log_query(endpoint, query, latency_ms, found=None, answer_mode=None, error=None, rewritten_query=None)
    outcome = "error"          if error is given (the request failed),
              "no_answer"      if retrieval found no adequate answer,
              "low_confidence" if figures were returned with confidence "low" (FR-002, FR-007),
              "answered"       otherwise.

A failure to WRITE the log never breaks the search itself: it is reported with
logging.warning and the learner still gets the answer (our choice, not a requirement).

Connection: the same POSTGRES_* settings as the loader and the search (ingestion/migrate.py).
Tests set query_log.DSN to their temporary database. conftest.py sets ENABLED = False for all
other tests, so test questions never end up in the real log (and in the analytics).
"""
import logging
import sys
import time
from functools import lru_cache
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

DSN = None      # None = the configured database; tests set their own
ENABLED = True  # False = write nothing (set by tests/conftest.py)

INSERT_SQL = """
    INSERT INTO query_log (endpoint, query, outcome, latency_ms, result_count, top_score, answer_mode, error,
                           rewritten_query)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""


@lru_cache(maxsize=1)
def _configured_dsn():
    return connection_string()


def elapsed_ms(start):
    """Milliseconds since start (a time.perf_counter() value), as a whole number."""
    return max(0, round((time.perf_counter() - start) * 1000))


def outcome_of(found, error=None):
    if error is not None:
        return "error"
    if found is None or found.get("reason") is not None:
        return "no_answer"
    if found.get("confidence") == "low":
        return "low_confidence"   # FR-007 lists it as its own outcome
    return "answered"


def log_query(endpoint, query, latency_ms, found=None, answer_mode=None, error=None, rewritten_query=None):
    """Write one row. Returns True if written, False if the log is disabled or could not be written.
    rewritten_query: /chat only, the standalone question searched for a follow-up (migration 009)."""
    if not ENABLED:
        return False
    results = (found or {}).get("results") or []
    row = (endpoint, query, outcome_of(found, error), int(latency_ms), len(results),
           results[0]["score"] if results else None, answer_mode,
           type(error).__name__ if error is not None else None, rewritten_query)
    try:
        with psycopg.connect(DSN or _configured_dsn()) as conn:
            conn.execute(INSERT_SQL, row)
        return True
    except (Exception, SystemExit) as exc:  # SystemExit: connection_string() exits if .env is incomplete
        logging.warning("query log not written (%s): %s", type(exc).__name__, exc)
        return False
