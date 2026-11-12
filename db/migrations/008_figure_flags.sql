-- 008: "Wrong figure" reports from learners (P7-38; FR-003, UC-03).
-- One row per report: the figure, the question it was returned for, who reported it and when,
-- an optional reason, and its status in the admin QA queue. UC-04 (later) closes reports.
CREATE TABLE figure_flags (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    figure_id   bigint      NOT NULL REFERENCES figures(id) ON DELETE CASCADE,
    user_id     bigint      NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    query       text        NOT NULL,              -- the question the figure was returned for
    reason      text,                              -- optional, typed by the learner
    status      text        NOT NULL DEFAULT 'open',
    flagged_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT figure_flags_query_valid  CHECK (btrim(query) <> '' AND char_length(query) <= 500),
    CONSTRAINT figure_flags_reason_valid CHECK (reason IS NULL OR (btrim(reason) <> '' AND char_length(reason) <= 500)),
    CONSTRAINT figure_flags_status_valid CHECK (status IN ('open', 'resolved'))
);

-- UC-03 A1: the same learner reporting the same figure for the same question is ONE report,
-- whatever the letter case or the spaces around the question.
CREATE UNIQUE INDEX figure_flags_one_per_question
    ON figure_flags (figure_id, user_id, lower(btrim(query)));

-- The QA queue lists the open reports, newest first.
CREATE INDEX figure_flags_open ON figure_flags (flagged_at) WHERE status = 'open';
