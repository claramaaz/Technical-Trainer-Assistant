-- 012: good / bad rating of a chat answer (P7-53; FR-010, supervisor meeting 13 Nov 2026).
-- One row per (answer, user): the answer is the query_log row of the question (POST /chat returns
-- its id as query_id). A learner can change the rating, never have two (FR-010 "it can be changed").
-- Read by the admin analytics page (P7-43): counts and the list of bad responses with their question.

CREATE TABLE answer_ratings (
    query_id  bigint      NOT NULL REFERENCES query_log(id) ON DELETE CASCADE,
    user_id   bigint      NOT NULL REFERENCES users(id)     ON DELETE CASCADE,
    rating    text        NOT NULL,
    rated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (query_id, user_id),
    CONSTRAINT answer_ratings_rating_valid CHECK (rating IN ('good', 'bad'))
);

CREATE INDEX answer_ratings_rated_at ON answer_ratings (rated_at);
