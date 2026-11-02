-- 001_init: extension, tables and searchable views (P7-15).
-- Applied by ingestion/migrate.py. Plain SQL. Do not edit after it has been applied
-- (add 002_*.sql instead; migrate.py refuses a changed file).
-- Embeddings are vector(384) (BAAI/bge-small-en-v1.5). Another model = a new migration.

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per handbook (BR-001: source URL, licence and retrieval date).
CREATE TABLE documents (
    id              text PRIMARY KEY,                 -- e.g. FAA-H-8083-15B
    title           text        NOT NULL,
    source_url      text        NOT NULL,
    licence         text,                             -- NULL = unknown
    retrieved_at    timestamptz NOT NULL,
    sha256          text,
    bytes           bigint,
    pdf_pages       integer,
    embedding_model text        NOT NULL,
    status          text        NOT NULL DEFAULT 'loading',
    loaded_at       timestamptz,
    CONSTRAINT documents_licence_not_blank CHECK (licence IS NULL OR btrim(licence) <> ''),
    CONSTRAINT documents_status_valid      CHECK (status IN ('loading', 'loaded', 'failed')),
    -- Searchable only with a known licence and a complete load (BR-001, UC-01 A2 and A4).
    searchable      boolean GENERATED ALWAYS AS (licence IS NOT NULL AND status = 'loaded') STORED
);

-- One row per PDF page: PDF position and printed number (SPEC 5.2).
CREATE TABLE pages (
    document_id    text    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    pdf_index      integer NOT NULL,                  -- 1-based position in the PDF
    printed_number text,                              -- e.g. 4-12; NULL on front matter
    text           text,                              -- NULL unless the page text is available
    PRIMARY KEY (document_id, pdf_index)
);

CREATE TABLE figures (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id    text    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    figure_number  text    NOT NULL,                  -- e.g. 4-12
    chapter        text    GENERATED ALWAYS AS (split_part(figure_number, '-', 1)) STORED,
    caption        text    NOT NULL,
    pdf_page       integer NOT NULL,
    printed_page   text    NOT NULL,                  -- the page cited to learners
    status         text    NOT NULL,
    needs_review   boolean NOT NULL DEFAULT false,
    rotation       smallint NOT NULL DEFAULT 0,
    bbox           double precision[],
    caption_bbox   double precision[],
    image_path     text    NOT NULL,                  -- relative path only; images are files, not in the database
    thumbnail_path text,
    search_text    text    NOT NULL,                  -- the figure document that was embedded (SPEC 5.1)
    embedding      vector(384) NOT NULL,
    UNIQUE (document_id, figure_number)
);

-- Paragraphs that reference a figure; position 0 is the first one.
CREATE TABLE figure_refs (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    figure_id    bigint   NOT NULL REFERENCES figures(id) ON DELETE CASCADE,
    position     smallint NOT NULL,
    pdf_page     integer  NOT NULL,
    printed_page text     NOT NULL,
    text         text     NOT NULL,
    UNIQUE (figure_id, position)
);

CREATE TABLE chunks (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id     text    NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id        text    NOT NULL,                 -- e.g. FAA-H-8083-15B-c0001
    chapter         text    NOT NULL,
    heading_path    text[]  NOT NULL,
    text            text    NOT NULL,
    embed_text      text    NOT NULL,                 -- heading + text, as embedded (SPEC 5.1)
    words           integer NOT NULL,
    pdf_pages       integer[] NOT NULL,
    printed_pages   text[]  NOT NULL,
    figure_mentions text[]  NOT NULL DEFAULT '{}',
    embedding       vector(384) NOT NULL,
    UNIQUE (document_id, chunk_id)
);

-- Search code reads ONLY these views, so the unknown-licence rule lives in one place.
CREATE VIEW searchable_figures AS
SELECT f.*, d.title AS handbook
FROM figures f
JOIN documents d ON d.id = f.document_id
WHERE d.searchable;

CREATE VIEW searchable_chunks AS
SELECT c.*, d.title AS handbook
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.searchable;
