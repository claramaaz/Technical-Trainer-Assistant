-- 013: an Admin closes a "Wrong figure" report after checking it (UC-04; FR-003).
-- A report is never deleted: it is marked resolved, with who closed it, when, and how
-- ("dismissed" = the figure was right, nothing to change; "corrected" is for the correction of UC-04,
-- a later ticket). A report never removed a figure from the answers: closing it changes only the queue.
ALTER TABLE figure_flags ADD COLUMN resolved_at timestamptz;
ALTER TABLE figure_flags ADD COLUMN resolved_by bigint REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE figure_flags ADD COLUMN resolution  text;
ALTER TABLE figure_flags ADD CONSTRAINT figure_flags_resolution_valid
    CHECK (resolution IS NULL OR resolution IN ('dismissed', 'corrected'));
