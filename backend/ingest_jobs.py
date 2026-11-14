"""Handbook upload by an Admin and the ingestion job that follows (P7-54; UC-01, FR-001, BR-001, BR-003;
supervisor meeting of 13 Nov 2026: "the admin uploads the documents from the interface").

save_upload(...)   checks the form and the file, writes data/raw/<id>.pdf and data/raw/<id>.meta.json
                   (source URL, licence, retrieval date, sha256: BR-001) and creates a job "queued".
start(job_id)      runs the job in a background thread. Jobs run ONE AT A TIME (a lock): ingestion is
                   heavy (PDF, images, embeddings) and two jobs would fight for the same CPU and files.
run_job(job_id)    the ingestion steps, the same commands as by hand (docs/LOCAL_DATA.md), in order.
                   Each step is a separate Python process: a crash in one step cannot stop the server,
                   and every step is exactly the script that was tested on its own.
list_jobs()        for the admin Sources panel (P7-40): newest first, with status and report.
mark_interrupted() at server start-up: a job left "queued" or "running" by a restart is marked failed.

A handbook becomes searchable only when load_db.py has finished (documents.status = 'loaded' and a
known licence: the searchable_* views, BR-001). A failed step leaves the earlier steps' results.
"""
import hashlib
import json
import re
import subprocess
import sys
import threading
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from backend import embedding

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingestion"))
from migrate import connection_string  # noqa: E402

DSN = None                       # None = the configured database; tests set their own
RAW_DIR = ROOT / "data" / "raw"
MAX_BYTES = 300 * 1024 * 1024    # the largest FAA handbooks are about 205 MB (brief section 2)
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,59}$")   # e.g. FAA-H-8083-3C
STEP_TIMEOUT_SECONDS = 2 * 60 * 60
ERROR_TAIL_CHARS = 2000

_lock = threading.Lock()


class UploadError(Exception):
    """The upload is refused; args[0] is a message for the admin, args[1] the HTTP status."""


def steps(handbook_id, model=None):
    """[(step name, command)] of the ingestion of one handbook, in order. Run from the repository root."""
    py, pdf = sys.executable, f"data/raw/{handbook_id}.pdf"
    bge = embedding.LOCAL_MODEL
    out = [
        ("inspect", [py, "ingestion/inspect_pdf.py", pdf]),
        ("extract figures", [py, "ingestion/extract_figures.py", pdf]),
        ("chunk text", [py, "ingestion/chunk_text.py", "chunk", pdf]),
        # bge vectors are still required by the loader (figures.embedding is NOT NULL, 001_init.sql)
        ("embed chunks (bge)", [py, "evaluation/baseline_retrieval.py", "embed", handbook_id, bge]),
        ("embed figures (bge)", [py, "evaluation/figure_retrieval.py", "embed", handbook_id, bge]),
        ("load database", [py, "ingestion/load_db.py", handbook_id]),
        ("page images", [py, "ingestion/render_pages.py", handbook_id]),
        ("thumbnails", [py, "ingestion/make_thumbnails.py", handbook_id]),
    ]
    model = model or embedding.configured_model()
    if embedding.is_api_model(model):
        # Same model at ingestion and at search time (supervisor, 13 Nov): the configured one.
        out.append((f"embed figures ({model})", [py, "ingestion/embed_text.py", model]))
    return out


def _connect():
    return psycopg.connect(DSN or connection_string())


def clean_form(handbook_id, title, source_url, licence, retrieved_at):
    """The form values, trimmed and checked (BR-001: source URL, licence and retrieval date required)."""
    handbook_id, title = (handbook_id or "").strip(), " ".join((title or "").split())
    source_url, licence = (source_url or "").strip(), " ".join((licence or "").split())
    if not ID_PATTERN.match(handbook_id) or ".." in handbook_id:
        raise UploadError("id: 3 to 60 letters, digits, '-', '_' or '.', for example FAA-H-8083-3C", 422)
    if not title or len(title) > 300:
        raise UploadError("title is required (at most 300 characters)", 422)
    if not re.match(r"^https?://\S+$", source_url) or len(source_url) > 1000:
        raise UploadError("source URL must start with http:// or https:// (BR-001)", 422)
    if not licence or licence.lower() == "unknown" or len(licence) > 300:
        raise UploadError("the licence is required: a document with an unknown licence is never searchable (BR-001)", 422)
    try:
        day = date.fromisoformat((retrieved_at or "").strip()) if (retrieved_at or "").strip() else date.today()
    except ValueError:
        raise UploadError("retrieval date must be YYYY-MM-DD", 422) from None
    if day > date.today():
        raise UploadError("the retrieval date cannot be in the future", 422)
    return handbook_id, title, source_url, licence, day


def _known(conn, handbook_id):
    if conn.execute("SELECT 1 FROM documents WHERE lower(id) = lower(%s)", (handbook_id,)).fetchone():
        return True
    return conn.execute("""SELECT 1 FROM ingestion_jobs WHERE lower(document_id) = lower(%s)
                           AND status IN ('queued', 'running')""", (handbook_id,)).fetchone() is not None


def save_upload(fileobj, handbook_id, title, source_url, licence, retrieved_at, user_id, raw_dir=None):
    """Check and store the upload, create the job. Returns the job id. Raises UploadError."""
    handbook_id, title, source_url, licence, day = clean_form(handbook_id, title, source_url, licence, retrieved_at)
    raw_dir = Path(raw_dir or RAW_DIR)
    with _connect() as conn:
        if _known(conn, handbook_id):
            raise UploadError(f"{handbook_id} is already loaded or being loaded", 409)
    raw_dir.mkdir(parents=True, exist_ok=True)
    pdf_path, partial = raw_dir / f"{handbook_id}.pdf", raw_dir / f"{handbook_id}.pdf.part"
    sha, size = hashlib.sha256(), 0
    try:
        with open(partial, "wb") as out:
            first = True
            while chunk := fileobj.read(1024 * 1024):
                if first and not chunk.startswith(b"%PDF-"):
                    raise UploadError("the file is not a PDF", 422)
                first = False
                size += len(chunk)
                if size > MAX_BYTES:
                    raise UploadError(f"the file is larger than {MAX_BYTES // (1024 * 1024)} MB", 413)
                sha.update(chunk)
                out.write(chunk)
        if size == 0:
            raise UploadError("the file is empty", 422)
        partial.replace(pdf_path)
    finally:
        partial.unlink(missing_ok=True)
    meta = {"id": handbook_id, "title": title, "source_url": source_url, "licence": licence,
            "retrieved_at": day.isoformat(), "bytes": size, "sha256": sha.hexdigest(),
            "uploaded_by_admin": True, "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (raw_dir / f"{handbook_id}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with _connect() as conn:
        return conn.execute("""INSERT INTO ingestion_jobs (document_id, title, steps_total, created_by)
                               VALUES (%s, %s, %s, %s) RETURNING id""",
                            (handbook_id, title, len(steps(handbook_id)), user_id)).fetchone()[0]


def _update(job_id, **fields):
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    with _connect() as conn:
        conn.execute(f"UPDATE ingestion_jobs SET {sets} WHERE id = %(id)s", dict(fields, id=job_id))


def read_report(handbook_id, root=None):
    path = Path(root or ROOT) / "data" / "extracted" / handbook_id / "report.json"
    if not path.exists():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    report.pop("thresholds", None)      # internal extractor settings, not useful on the admin page
    return report


def reindex_steps(handbook_id):
    """P7-32 (FR-008, UC-10): one step, ingestion/reindex.py, for one handbook or "ALL"."""
    return [("re-index", [sys.executable, "ingestion/reindex.py", handbook_id])]


def create_reindex_job(handbook_id, user_id):
    """A re-index job, shown with the ingestion jobs (title "Re-index"). Returns its id. Raises UploadError."""
    with _connect() as conn:
        if handbook_id != "ALL" and not conn.execute("SELECT 1 FROM documents WHERE id = %s", (handbook_id,)).fetchone():
            raise UploadError(f"{handbook_id} is not loaded", 404)
        if conn.execute("SELECT 1 FROM ingestion_jobs WHERE status IN ('queued', 'running')").fetchone():
            raise UploadError("another ingestion or re-index job is running: wait until it ends", 409)
        return conn.execute("""INSERT INTO ingestion_jobs (document_id, title, steps_total, created_by)
                               VALUES (%s, 'Re-index', 1, %s) RETURNING id""", (handbook_id, user_id)).fetchone()[0]


def run_job(job_id, run=subprocess.run, on_done=None, todo=None):
    """Run every step of the job. A step that exits with an error stops the job ("failed").
    todo: the steps; default = the ingestion steps of the job's handbook."""
    with _connect() as conn:
        handbook_id = conn.execute("SELECT document_id FROM ingestion_jobs WHERE id = %s", (job_id,)).fetchone()[0]
    todo = todo or steps(handbook_id)
    _update(job_id, status="running", started_at=datetime.now(timezone.utc), steps_total=len(todo))
    for done, (name, command) in enumerate(todo):
        _update(job_id, step=name, steps_done=done)
        try:
            result = run(command, cwd=ROOT, capture_output=True, text=True, timeout=STEP_TIMEOUT_SECONDS)
            failed, output = result.returncode != 0, (result.stdout or "") + (result.stderr or "")
        except (OSError, subprocess.TimeoutExpired) as exc:
            failed, output = True, f"{type(exc).__name__}: {exc}"
        if name == "extract figures" and not failed:
            report = read_report(handbook_id)
            if report is not None:
                _update(job_id, report=Jsonb(report))
        if failed:
            _update(job_id, status="failed", error=(output.strip()[-ERROR_TAIL_CHARS:] or "the step failed"),
                    finished_at=datetime.now(timezone.utc))
            return False
    _update(job_id, status="done", step=None, steps_done=len(todo), finished_at=datetime.now(timezone.utc))
    if on_done:
        on_done()
    return True


def _refresh_search_index():
    """The search keeps its list of figures in memory (load_index, lru_cache): reload it so the new
    handbook is searchable without restarting the server."""
    from backend import retrieval
    retrieval.load_index.cache_clear()


def start(job_id, todo=None):
    def worker():
        with _lock:
            try:
                run_job(job_id, on_done=_refresh_search_index, todo=todo)
            except Exception as exc:     # never leave a job "running" because of a bug or a lost database
                try:
                    _update(job_id, status="failed", error=f"{type(exc).__name__}: {exc}"[:ERROR_TAIL_CHARS],
                            finished_at=datetime.now(timezone.utc))
                except Exception:
                    pass
    thread = threading.Thread(target=worker, name=f"ingestion-job-{job_id}", daemon=True)
    thread.start()
    return thread


JOBS_SQL = """
    SELECT j.id, j.document_id, j.title, j.status, j.step, j.steps_done, j.steps_total, j.error, j.report,
           j.created_at, j.started_at, j.finished_at, u.email,
           d.status AS document_status, d.searchable,
           (SELECT count(*) FROM figures f WHERE f.document_id = j.document_id) AS figures
    FROM ingestion_jobs j
    LEFT JOIN users u ON u.id = j.created_by
    LEFT JOIN documents d ON d.id = j.document_id
    ORDER BY j.created_at DESC, j.id DESC
    LIMIT 100"""

DOCUMENTS_SQL = """
    SELECT d.id, d.title, d.source_url, d.licence, d.retrieved_at, d.status, d.searchable, d.pdf_pages,
           (SELECT count(*) FROM figures f WHERE f.document_id = d.id) AS figures,
           (SELECT count(*) FROM figures f WHERE f.document_id = d.id AND f.needs_review) AS needs_review
    FROM documents d ORDER BY d.id"""


def _rows(sql, params=()):
    with _connect() as conn:
        cur = conn.execute(sql, params)
        names = [c.name for c in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]


def list_jobs():
    return _rows(JOBS_SQL)


def get_job(job_id):
    rows = [j for j in _rows(JOBS_SQL.replace("ORDER BY", "WHERE j.id = %s ORDER BY"), (job_id,))]
    return rows[0] if rows else None


def list_documents():
    return _rows(DOCUMENTS_SQL)


def mark_interrupted():
    """At start-up: jobs left queued/running by a stopped server can never finish. Returns how many."""
    with _connect() as conn:
        return conn.execute("""UPDATE ingestion_jobs SET status = 'failed', finished_at = now(),
                               error = 'the server stopped before the job finished: upload the PDF again'
                               WHERE status IN ('queued', 'running')""").rowcount
