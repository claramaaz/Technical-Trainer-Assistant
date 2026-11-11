-- 006: an image embedding for every figure, for joint text + image retrieval (P7-30;
-- brief section 4 "Joint retrieval over text and images", section 7 weeks 7-8).
-- The vector is computed from the figure IMAGE (the PNG file), not from its caption, with
-- sentence-transformers "clip-ViT-B-32" (512 dimensions). It is filled by ingestion/embed_images.py.
-- A separate table, not a new column of figures: the text search keeps working when no image
-- embedding has been computed yet, and the model used is recorded per row.
-- Reloading a handbook with load_db.py deletes its figures, so their image embeddings go too
-- (ON DELETE CASCADE): run ingestion/embed_images.py again after a reload.

CREATE TABLE figure_image_embeddings (
    figure_id   bigint      PRIMARY KEY REFERENCES figures(id) ON DELETE CASCADE,
    model       text        NOT NULL,
    embedding   vector(512) NOT NULL,
    embedded_at timestamptz NOT NULL DEFAULT now()
);

-- Search code reads only searchable_* views (BR-001): the image of a figure whose handbook has an
-- unknown licence, or is not fully loaded, is never ranked. Joined to searchable_figures, so the
-- licence rule stays in one place.
CREATE VIEW searchable_figure_images AS
SELECT e.figure_id AS id, e.model, e.embedding, f.document_id
FROM figure_image_embeddings e
JOIN searchable_figures f ON f.id = e.figure_id;
