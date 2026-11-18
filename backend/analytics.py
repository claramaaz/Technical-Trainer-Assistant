"""Admin analytics (P7-43; FR-007, UC-09, FR-010; brief section 1). Reads the query log written by
backend/query_log.py (P7-28) and the answer ratings of backend/ratings.py (P7-53).

summary(start, end) -> dict, for the days start..end INCLUDED (dates, UTC):
    totals        questions, and how many ended answered / low_confidence / no_answer / error
    failure_rate  questions ending in an error / questions (FR-007 defines it this way); None if 0
    no_answer_rate  questions with no answer found / questions; None if 0
    latency_ms    average, median (p50), p95 and maximum, over the questions that did not fail
    per_day       one row per day of the period (days without questions included, with 0)
    by_endpoint   questions per route (chat, answer, search)
    unanswered    the questions with no answer found, newest first (UC-09 step 2), with what is
                  needed to see what happened (UC-09 step 3): the question actually searched,
                  best score, latency, answer mode
    failed        the questions that ended in an error, newest first (exception class only)
    ratings       good / bad counts of the answers asked in the period (FR-010)
    bad_responses the answers rated bad, newest first, with their question (FR-010)

A day is a UTC day: the server and the database both work in UTC, and the page shows the period it
asked for, so the numbers do not change with the admin's time zone.
"""
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

DSN = None   # None = the configured database; tests set their own

MAX_DAYS = 366
MAX_LISTED = 200
OUTCOMES = ("answered", "low_confidence", "no_answer", "error")


class PeriodError(ValueError):
    """The period asked for cannot be used; the message is shown to the admin."""


def _connect():
    return psycopg.connect(DSN or connection_string())


def check_period(start, end, today=None):
    """(start, end) as dates. Refuses an end before the start, a future start or a period too long."""
    today = today or datetime.now(timezone.utc).date()
    if end < start:
        raise PeriodError("the end of the period is before its start")
    if start > today:
        raise PeriodError("the period starts in the future")
    if (end - start).days + 1 > MAX_DAYS:
        raise PeriodError(f"the period is longer than {MAX_DAYS} days")
    return start, end


def _bounds(start, end):
    return (datetime.combine(start, time.min, tzinfo=timezone.utc),
            datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc))


def _rate(part, whole):
    return round(part / whole, 4) if whole else None


TOTALS_SQL = """
    SELECT count(*),
           count(*) FILTER (WHERE outcome = 'answered'),
           count(*) FILTER (WHERE outcome = 'low_confidence'),
           count(*) FILTER (WHERE outcome = 'no_answer'),
           count(*) FILTER (WHERE outcome = 'error'),
           round(avg(latency_ms) FILTER (WHERE outcome <> 'error')),
           percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE outcome <> 'error'),
           percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE outcome <> 'error'),
           max(latency_ms) FILTER (WHERE outcome <> 'error')
    FROM query_log WHERE asked_at >= %s AND asked_at < %s"""

PER_DAY_SQL = """
    SELECT d::date AS day,
           count(q.id),
           count(q.id) FILTER (WHERE q.outcome = 'no_answer'),
           count(q.id) FILTER (WHERE q.outcome = 'error'),
           percentile_cont(0.5) WITHIN GROUP (ORDER BY q.latency_ms) FILTER (WHERE q.outcome <> 'error')
    FROM generate_series(%s::date, %s::date, interval '1 day') AS d
    LEFT JOIN query_log q
           ON q.asked_at >= (d AT TIME ZONE 'UTC') AND q.asked_at < ((d + interval '1 day') AT TIME ZONE 'UTC')
    GROUP BY d ORDER BY d"""

BY_ENDPOINT_SQL = """
    SELECT endpoint, count(*) FROM query_log WHERE asked_at >= %s AND asked_at < %s
    GROUP BY endpoint ORDER BY endpoint"""

LIST_SQL = """
    SELECT id, asked_at, endpoint, query, rewritten_query, outcome, latency_ms, result_count, top_score,
           answer_mode, error
    FROM query_log WHERE asked_at >= %s AND asked_at < %s AND outcome = %s
    ORDER BY asked_at DESC, id DESC LIMIT %s"""

RATINGS_SQL = """
    SELECT count(*) FILTER (WHERE r.rating = 'good'), count(*) FILTER (WHERE r.rating = 'bad')
    FROM answer_ratings r JOIN query_log q ON q.id = r.query_id
    WHERE q.asked_at >= %s AND q.asked_at < %s"""

BAD_SQL = """
    SELECT q.id, q.asked_at, q.query, q.rewritten_query, q.answer_mode, q.outcome, r.rated_at, u.email
    FROM answer_ratings r
    JOIN query_log q ON q.id = r.query_id
    JOIN users u ON u.id = r.user_id
    WHERE r.rating = 'bad' AND q.asked_at >= %s AND q.asked_at < %s
    ORDER BY r.rated_at DESC, q.id DESC LIMIT %s"""


def _ms(value):
    return None if value is None else int(round(value))


def _question(row):
    (qid, asked_at, endpoint, query, rewritten, outcome, latency, results, top_score, mode, error) = row
    return {"id": qid, "asked_at": asked_at.isoformat(), "endpoint": endpoint, "query": query,
            "rewritten_query": rewritten, "outcome": outcome, "latency_ms": latency,
            "result_count": results, "top_score": None if top_score is None else round(float(top_score), 3),
            "answer_mode": mode, "error": error}


def summary(start, end, limit=MAX_LISTED):
    lo, hi = _bounds(start, end)
    with _connect() as conn:
        (total, answered, low, no_answer, error, avg_ms, p50, p95, max_ms) = conn.execute(TOTALS_SQL, (lo, hi)).fetchone()
        per_day = [{"day": day.isoformat(), "questions": n, "no_answer": na, "errors": err, "p50_ms": _ms(med)}
                   for (day, n, na, err, med) in conn.execute(PER_DAY_SQL, (start, end)).fetchall()]
        by_endpoint = dict(conn.execute(BY_ENDPOINT_SQL, (lo, hi)).fetchall())
        unanswered = [_question(r) for r in conn.execute(LIST_SQL, (lo, hi, "no_answer", limit)).fetchall()]
        failed = [_question(r) for r in conn.execute(LIST_SQL, (lo, hi, "error", limit)).fetchall()]
        good, bad = conn.execute(RATINGS_SQL, (lo, hi)).fetchone()
        bad_responses = [{"query_id": qid, "asked_at": asked.isoformat(), "query": query,
                          "rewritten_query": rewritten, "answer_mode": mode, "outcome": outcome,
                          "rated_at": rated.isoformat(), "rated_by": email}
                         for (qid, asked, query, rewritten, mode, outcome, rated, email)
                         in conn.execute(BAD_SQL, (lo, hi, limit)).fetchall()]
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "days": (end - start).days + 1},
        "totals": {"questions": total, "answered": answered, "low_confidence": low,
                   "no_answer": no_answer, "error": error},
        "failure_rate": _rate(error, total),
        "no_answer_rate": _rate(no_answer, total),
        "latency_ms": {"average": _ms(avg_ms), "p50": _ms(p50), "p95": _ms(p95), "max": _ms(max_ms)},
        "per_day": per_day,
        "by_endpoint": by_endpoint,
        "unanswered": unanswered,
        "failed": failed,
        "ratings": {"good": good, "bad": bad},
        "bad_responses": bad_responses,
    }


def parse_day(text, name):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        raise PeriodError(f"{name} must be a date written YYYY-MM-DD") from None
