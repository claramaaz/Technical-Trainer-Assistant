"""Admin upload and ingestion job (P7-54; UC-01, FR-001, BR-001, BR-003).

API tests replace backend/ingest_jobs.py functions by fakes (no database, no real ingestion).
Database tests use the temporary database of conftest.py and a FAKE step runner, so no PDF is
processed; they are skipped if PostgreSQL is not running.
"""
import io
import json
import subprocess
import sys
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import auth, embedding, ingest_jobs
from backend.app import app
from backend.ingest_jobs import UploadError, clean_form

client = TestClient(app)
PDF = b"%PDF-1.7\n fake handbook content \n%%EOF\n"
FORM = {"id": "FAA-H-8083-3C", "title": "Airplane Flying Handbook",
        "source_url": "https://www.faa.gov/airplane_handbook.pdf",
        "licence": "United States Government work, public domain", "retrieved_at": "2026-11-13"}


@pytest.fixture
def as_admin():
    app.dependency_overrides[auth.current_user] = lambda: {"id": 7, "email": "admin@test", "role": "admin"}
    yield
    app.dependency_overrides[auth.current_user] = lambda: {"id": 0, "email": "test@learner", "role": "learner"}


# ---- the form (BR-001) ----

def test_valid_form_is_trimmed():
    out = clean_form("  FAA-H-8083-3C ", "  Airplane   Flying Handbook ", " https://faa.gov/a.pdf ",
                     " public  domain ", "2026-11-13")
    assert out == ("FAA-H-8083-3C", "Airplane Flying Handbook", "https://faa.gov/a.pdf", "public domain",
                   date(2026, 11, 13))


def test_missing_date_means_today():
    assert clean_form("ABC-1", "t", "https://x.y/z.pdf", "pd", "")[4] == date.today()


@pytest.mark.parametrize("field, value, words", [
    ("handbook_id", "../etc", "id"), ("handbook_id", "a", "id"), ("handbook_id", "x/y", "id"),
    ("title", "  ", "title"), ("source_url", "ftp://x", "URL"), ("source_url", "", "URL"),
    ("licence", "", "licence"), ("licence", "Unknown", "licence"),
    ("retrieved_at", "13/11/2026", "date"), ("retrieved_at", (date.today() + timedelta(days=1)).isoformat(), "future"),
])
def test_bad_form_is_refused_with_a_clear_message(field, value, words):
    values = {"handbook_id": "FAA-H-8083-3C", "title": "t", "source_url": "https://x.y/z.pdf",
              "licence": "pd", "retrieved_at": "2026-11-13"}
    values[field] = value
    with pytest.raises(UploadError) as err:
        clean_form(**values)
    assert words in err.value.args[0] and err.value.args[1] == 422


# ---- the steps ----

def test_steps_are_the_manual_pipeline_in_order_and_use_the_configured_api_model(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "gemini-embedding-001")
    names = [name for name, _cmd in ingest_jobs.steps("FAA-H-8083-3C")]
    assert names == ["inspect", "extract figures", "chunk text", "embed chunks (bge)", "embed figures (bge)",
                     "load database", "page images", "thumbnails", "embed figures (gemini-embedding-001)"]
    commands = dict(ingest_jobs.steps("FAA-H-8083-3C"))
    assert commands["extract figures"] == [sys.executable, "ingestion/extract_figures.py", "data/raw/FAA-H-8083-3C.pdf"]
    assert commands["embed figures (gemini-embedding-001)"][-1] == "gemini-embedding-001"


def test_no_api_embedding_step_with_bge():
    assert all("gemini" not in name for name, _cmd in ingest_jobs.steps("X-1", embedding.LOCAL_MODEL))


def test_report_hides_the_extractor_settings(tmp_path):
    folder = tmp_path / "data" / "extracted" / "X-1"
    folder.mkdir(parents=True)
    (folder / "report.json").write_text(json.dumps({"pdf_pages": 9, "captions_found": 3, "thresholds": {}}))
    assert ingest_jobs.read_report("X-1", tmp_path) == {"pdf_pages": 9, "captions_found": 3}
    assert ingest_jobs.read_report("NONE", tmp_path) is None


# ---- the routes ----

def test_learner_cannot_upload_or_list():
    files = {"file": ("h.pdf", PDF, "application/pdf")}
    assert client.post("/admin/documents", data=FORM, files=files).status_code == 403
    assert client.get("/admin/documents").status_code == 403
    assert client.get("/admin/ingestion-jobs/1").status_code == 403


def test_admin_upload_stores_and_starts_the_job(as_admin, monkeypatch):
    seen, started = [], []
    monkeypatch.setattr(ingest_jobs, "save_upload",
                        lambda f, *args: seen.append((f.read(), args)) or 42)
    monkeypatch.setattr(ingest_jobs, "start", started.append)
    r = client.post("/admin/documents", data=FORM, files={"file": ("h.pdf", PDF, "application/pdf")})
    assert r.status_code == 202 and r.json() == {"job_id": 42, "status": "queued"}
    assert seen == [(PDF, ("FAA-H-8083-3C", "Airplane Flying Handbook", FORM["source_url"], FORM["licence"],
                           "2026-11-13", 7))]
    assert started == [42]


@pytest.mark.parametrize("message, status", [("the file is not a PDF", 422), ("already loaded", 409)])
def test_upload_error_becomes_its_http_status(as_admin, monkeypatch, message, status):
    def refuse(*_a):
        raise UploadError(message, status)
    monkeypatch.setattr(ingest_jobs, "save_upload", refuse)
    monkeypatch.setattr(ingest_jobs, "start", lambda job: pytest.fail("job started"))
    r = client.post("/admin/documents", data=FORM, files={"file": ("h.pdf", PDF, "application/pdf")})
    assert r.status_code == status and r.json()["detail"] == message


def test_missing_file_or_licence_field_is_422(as_admin):
    assert client.post("/admin/documents", data=FORM).status_code == 422
    form = {k: v for k, v in FORM.items() if k != "licence"}
    assert client.post("/admin/documents", data=form,
                       files={"file": ("h.pdf", PDF, "application/pdf")}).status_code == 422


def test_unknown_job_is_404(as_admin, monkeypatch):
    monkeypatch.setattr(ingest_jobs, "get_job", lambda job_id: None)
    assert client.get("/admin/ingestion-jobs/999").status_code == 404


# ---- with the temporary database ----

@pytest.fixture
def jobs_db(db, pg_test_dsn, monkeypatch, tmp_path):
    monkeypatch.setattr(ingest_jobs, "DSN", pg_test_dsn)
    monkeypatch.setenv("EMBEDDING_MODEL", embedding.LOCAL_MODEL)
    db.execute("TRUNCATE ingestion_jobs")
    db.commit()
    return tmp_path


def upload(raw_dir, content=PDF, handbook_id="TEST-HB-1"):
    return ingest_jobs.save_upload(io.BytesIO(content), handbook_id, "Test handbook", "https://x.y/t.pdf",
                                   "public domain", "2026-11-13", None, raw_dir=raw_dir)


def job(db, job_id):
    db.commit()   # see the other connections' writes
    return db.execute("SELECT status, step, steps_done, steps_total, error, report FROM ingestion_jobs WHERE id = %s",
                      (job_id,)).fetchone()


def test_upload_writes_pdf_meta_and_a_queued_job(jobs_db, db):
    job_id = upload(jobs_db)
    assert (jobs_db / "TEST-HB-1.pdf").read_bytes() == PDF
    meta = json.loads((jobs_db / "TEST-HB-1.meta.json").read_text())
    assert meta["licence"] == "public domain" and meta["retrieved_at"] == "2026-11-13" and meta["uploaded_by_admin"]
    assert len(meta["sha256"]) == 64 and meta["bytes"] == len(PDF)
    assert job(db, job_id)[:4] == ("queued", None, 0, 8)


def test_not_a_pdf_is_refused_and_nothing_is_kept(jobs_db, db):
    with pytest.raises(UploadError, match="not a PDF"):
        upload(jobs_db, b"<html>hello</html>")
    assert list(jobs_db.iterdir()) == [] and db.execute("SELECT count(*) FROM ingestion_jobs").fetchone()[0] == 0


def test_same_handbook_while_a_job_is_queued_is_409(jobs_db):
    upload(jobs_db)
    with pytest.raises(UploadError) as err:
        upload(jobs_db, handbook_id="test-hb-1")
    assert err.value.args[1] == 409


def test_job_runs_every_step_then_done(jobs_db, db, monkeypatch):
    monkeypatch.setattr(ingest_jobs, "read_report", lambda hid: {"captions_found": 3})
    job_id, ran, refreshed = upload(jobs_db), [], []
    fake = lambda cmd, **kw: ran.append(cmd) or subprocess.CompletedProcess(cmd, 0, "ok", "")
    assert ingest_jobs.run_job(job_id, run=fake, on_done=lambda: refreshed.append(1)) is True
    assert len(ran) == 8 and refreshed == [1]
    assert job(db, job_id) == ("done", None, 8, 8, None, {"captions_found": 3})


def test_failed_step_stops_the_job_and_keeps_the_end_of_its_output(jobs_db, db):
    job_id, ran = upload(jobs_db), []

    def fake(cmd, **kw):
        ran.append(cmd)
        code = 1 if "chunk_text.py" in cmd[1] else 0
        return subprocess.CompletedProcess(cmd, code, "x" * 3000, "Traceback: boom")
    assert ingest_jobs.run_job(job_id, run=fake, on_done=lambda: pytest.fail("not done")) is False
    status, step, steps_done, _total, error, _report = job(db, job_id)
    assert (status, step, steps_done, len(ran)) == ("failed", "chunk text", 2, 3)
    assert error.endswith("Traceback: boom") and len(error) == ingest_jobs.ERROR_TAIL_CHARS


def test_restart_marks_unfinished_jobs_failed(jobs_db, db):
    job_id = upload(jobs_db)
    assert ingest_jobs.mark_interrupted() == 1
    assert job(db, job_id)[0] == "failed" and "upload the PDF again" in job(db, job_id)[4]
