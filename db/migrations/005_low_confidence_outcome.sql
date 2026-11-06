-- 005: the query log also records low-confidence answers (P7-48; FR-007 lists the outcomes
-- answered, low confidence, no answer found, error; FR-002 defines the low-confidence match).
ALTER TABLE query_log DROP CONSTRAINT query_log_outcome_valid;
ALTER TABLE query_log ADD CONSTRAINT query_log_outcome_valid
    CHECK (outcome IN ('answered', 'low_confidence', 'no_answer', 'error'));
