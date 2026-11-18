-- 009: the query log also records chat questions (P7-51; FR-007, FR-009, supervisor meeting 13 Nov 2026).
-- endpoint 'chat' = POST /chat. rewritten_query = the standalone question searched for a follow-up
-- (NULL when the message was searched as it is), so the analytics can show what was really searched.
ALTER TABLE query_log DROP CONSTRAINT query_log_endpoint_valid;
ALTER TABLE query_log ADD CONSTRAINT query_log_endpoint_valid
    CHECK (endpoint IN ('search', 'answer', 'chat'));
ALTER TABLE query_log ADD COLUMN rewritten_query text;
