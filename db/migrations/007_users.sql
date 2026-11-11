-- 007: user accounts for login (P7-35; FR-004, UC-05, BR-003).
-- Two roles only: a Learner searches; an Admin also gets the admin screens.
-- The password is never stored, only its bcrypt hash (backend/auth.py).
-- Emails are stored in lower case (create_user.py and /login lower-case them), so the
-- UNIQUE constraint also stops "Mia@x.com" and "mia@x.com" from being two accounts.
CREATE TABLE users (
    id            bigserial PRIMARY KEY,
    email         text NOT NULL UNIQUE CHECK (email = lower(email)),
    password_hash text NOT NULL,
    role          text NOT NULL CHECK (role IN ('learner', 'admin')),
    created_at    timestamptz NOT NULL DEFAULT now()
);
