-- 011: ingestion jobs started by an Admin from the web interface (P7-54; UC-01, FR-001, BR-001, BR-003;
-- supervisor meeting 13 Nov 2026: "the admin uploads the documents from the interface").
-- One row per uploaded handbook. backend/ingest_jobs.py runs the ingestion steps one after the other
-- and records here where it is, so the admin page can show queued / running / done / failed, and the
-- extraction report (pages, captions, bound figures, unbound regions, figures flagged for review).

CREATE TABLE ingestion_jobs (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id  text        NOT NULL,
    title        text        NOT NULL,
    status       text        NOT NULL DEFAULT 'queued',
    step         text,                               -- the step running, or the one that failed
    steps_done   smallint    NOT NULL DEFAULT 0,
    steps_total  smallint    NOT NULL,
    error        text,                               -- last lines of the failed step's output
    report       jsonb,                              -- data/extracted/<id>/report.json when known
    created_by   bigint      REFERENCES users(id) ON DELETE SET NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    started_at   timestamptz,
    finished_at  timestamptz,
    CONSTRAINT ingestion_jobs_status_valid CHECK (status IN ('queued', 'running', 'done', 'failed')),
    CONSTRAINT ingestion_jobs_error_iff    CHECK ((status = 'failed') = (error IS NOT NULL))
);

CREATE INDEX ingestion_jobs_created_at ON ingestion_jobs (created_at DESC);
