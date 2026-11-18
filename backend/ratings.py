"""Good / bad rating of a chat answer (P7-53; FR-010, supervisor meeting of 13 Nov 2026).

save_rating(query_id, user_id, rating)   stores the rating of one answer by one user. Rating the same
                                         answer again replaces the first rating (FR-010: "it can be
                                         changed"); there is never more than one row per user and answer.
                                         Returns SAVED, UNKNOWN_ANSWER or UNKNOWN_USER.

The answer is identified by its query_log id, which POST /chat returns as query_id. Only chat answers
can be rated: a /search or /answer row has no answer shown with good / bad buttons.
Table: answer_ratings (db/migrations/012_answer_ratings.sql). The admin side reads it in
backend/analytics.py (counts and the list of bad responses, P7-43).
"""
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

DSN = None   # None = the configured database; tests set their own

RATINGS = ("good", "bad")
SAVED = "saved"
UNKNOWN_ANSWER = "unknown_answer"
UNKNOWN_USER = "unknown_user"     # a valid token for an account deleted since the login


def _connect():
    return psycopg.connect(DSN or connection_string())


def save_rating(query_id, user_id, rating):
    if rating not in RATINGS:
        raise ValueError(f"rating must be one of {RATINGS}")
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM query_log WHERE id = %s AND endpoint = 'chat'", (query_id,))
        if cur.fetchone() is None:
            return UNKNOWN_ANSWER
        try:
            cur.execute("""INSERT INTO answer_ratings (query_id, user_id, rating) VALUES (%s, %s, %s)
                           ON CONFLICT (query_id, user_id)
                           DO UPDATE SET rating = EXCLUDED.rating, rated_at = now()""",
                        (query_id, user_id, rating))
        except psycopg.errors.ForeignKeyViolation:
            conn.rollback()
            return UNKNOWN_USER
    return SAVED
