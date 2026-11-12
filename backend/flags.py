"""Learner reports of a wrong figure, and the list the admin QA queue reads (P7-38; FR-003, UC-03).

save_flag   stores one report (UC-03 step 3): the figure, the question, the user and the time,
            with an optional reason. A second report of the same figure by the same learner for
            the same question is not stored again (UC-03 A1).
open_flags  the reports still open, newest first, with what an admin needs to judge them:
            figure, caption, handbook, printed page, question, reason, who and when.

Table: figure_flags (db/migrations/008_figure_flags.sql). Only figures that are searchable
(searchable_figures) can be reported: a learner can only have seen those.
"""
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

DSN = None   # None = the configured database; tests set their own

CREATED = "created"
DUPLICATE = "duplicate"
UNKNOWN_FIGURE = "unknown_figure"
UNKNOWN_USER = "unknown_user"     # a valid token for an account deleted since the login

MAX_LISTED = 200


def _connect():
    return psycopg.connect(DSN or connection_string())


def clean_reason(reason):
    """The reason without surrounding spaces, or None when nothing was typed."""
    reason = (reason or "").strip()
    return reason or None


def save_flag(figure_id, user_id, query, reason=None):
    """Store one report. Returns CREATED, DUPLICATE, UNKNOWN_FIGURE or UNKNOWN_USER."""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM searchable_figures WHERE id = %s", (figure_id,))
        if cur.fetchone() is None:
            return UNKNOWN_FIGURE
        try:
            # ON CONFLICT DO NOTHING: the unique index figure_flags_one_per_question
            # turns a repeated report into "nothing inserted" instead of an error.
            cur.execute("""INSERT INTO figure_flags (figure_id, user_id, query, reason)
                           VALUES (%s, %s, %s, %s)
                           ON CONFLICT DO NOTHING
                           RETURNING id""", (figure_id, user_id, query, reason))
        except psycopg.errors.ForeignKeyViolation:
            conn.rollback()
            return UNKNOWN_USER
        return CREATED if cur.fetchone() is not None else DUPLICATE


def open_flags(limit=MAX_LISTED):
    """The open reports, newest first (at most `limit`), as dicts ready for JSON."""
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT fl.id, fl.figure_id, f.figure_number, f.caption, d.title, f.printed_page,
                   f.thumbnail_path IS NOT NULL, fl.query, fl.reason, u.email, fl.flagged_at,
                   count(*) OVER (PARTITION BY fl.figure_id)
            FROM figure_flags fl
            JOIN figures   f ON f.id = fl.figure_id
            JOIN documents d ON d.id = f.document_id
            JOIN users     u ON u.id = fl.user_id
            WHERE fl.status = 'open'
            ORDER BY fl.flagged_at DESC, fl.id DESC
            LIMIT %s""", (limit,))
        rows = cur.fetchall()
    return [{
        "id": flag_id,
        "figure_id": fid,
        "figure_number": number,
        "caption": caption,
        "handbook": handbook,
        "printed_page": page,
        "image_url": f"/figures/{fid}/image",
        "thumbnail_url": f"/figures/{fid}/thumbnail" if has_thumbnail else None,
        "query": query,
        "reason": reason,
        "reported_by": email,
        "flagged_at": flagged_at.isoformat(),
        "reports_for_figure": reports,   # open reports of this figure, all questions together
    } for (flag_id, fid, number, caption, handbook, page, has_thumbnail, query, reason, email,
           flagged_at, reports) in rows]
