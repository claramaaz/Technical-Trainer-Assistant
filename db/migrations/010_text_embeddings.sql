-- 010: text embeddings made by an API model (P7-57; supervisor meeting 13 Nov 2026: "a small hosted
-- embedding model, OpenAI or Gemini, check which one suits your data best").
-- One row per (figure or chunk, model), so gemini-embedding-001 and text-embedding-3-small can be
-- compared with bge-small (figures.embedding, 384) on the same data. Filled by ingestion/embed_text.py
-- with the SAME text that bge embedded (figures.search_text, chunks.embed_text).
-- Both API models are asked for 768 dimensions. Reloading a handbook deletes its figures and chunks,
-- so their embeddings go too (ON DELETE CASCADE): run embed_text.py again after a reload.

CREATE TABLE figure_text_embeddings (
    figure_id   bigint      NOT NULL REFERENCES figures(id) ON DELETE CASCADE,
    model       text        NOT NULL,
    embedding   vector(768) NOT NULL,
    embedded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (figure_id, model)
);

CREATE TABLE chunk_text_embeddings (
    chunk_id    bigint      NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    model       text        NOT NULL,
    embedding   vector(768) NOT NULL,
    embedded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (chunk_id, model)
);

-- Search reads only searchable_* views (BR-001), joined to the existing views so the licence rule
-- stays in one place.
CREATE VIEW searchable_figure_text AS
SELECT e.figure_id AS id, e.model, e.embedding, f.document_id
FROM figure_text_embeddings e
JOIN searchable_figures f ON f.id = e.figure_id;

CREATE VIEW searchable_chunk_text AS
SELECT e.chunk_id AS id, e.model, e.embedding, c.document_id, c.figure_mentions
FROM chunk_text_embeddings e
JOIN searchable_chunks c ON c.id = e.chunk_id;
