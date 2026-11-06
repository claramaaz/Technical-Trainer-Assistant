-- 003: one row per question asked (P7-28; FR-007, UC-02 postconditions, UC-09).
-- Written by backend/query_log.py on every GET /search and GET /answer.
-- Read by the admin analytics page (volume, latency, failure rate, unanswered questions).
-- A blank query rejected with 422 is not a question and is not logged.

CREATE TABLE query_log (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asked_at     timestamptz NOT NULL DEFAULT now(),
    endpoint     text        NOT NULL,             -- search | answer
    query        text        NOT NULL,             -- the question, trimmed
    outcome      text        NOT NULL,             -- answered | no_answer | error (FR-007)
    latency_ms   integer     NOT NULL,             -- measured on the server, whole request
    result_count smallint    NOT NULL DEFAULT 0,   -- figures returned
    top_score    real,                             -- best similarity; NULL when nothing returned
    answer_mode  text,                             -- /answer only: llm | extractive | no_answer
    error        text,                             -- exception class name only, never a message
    CONSTRAINT query_log_endpoint_valid CHECK (endpoint IN ('search', 'answer')),
    CONSTRAINT query_log_outcome_valid  CHECK (outcome IN ('answered', 'no_answer', 'error')),
    CONSTRAINT query_log_latency_valid  CHECK (latency_ms >= 0),
    CONSTRAINT query_log_error_iff      CHECK ((outcome = 'error') = (error IS NOT NULL))
);

-- The analytics page always filters by period.
CREATE INDEX query_log_asked_at ON query_log (asked_at);
