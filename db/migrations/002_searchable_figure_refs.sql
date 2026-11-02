-- 002: view for the paragraphs that cite a figure (P7-22).
-- Search shows the first citing paragraph as the "passage". It must not read the raw
-- table figure_refs, so the unknown-licence / not-loaded rule is applied here too,
-- in the same way as in searchable_figures (001_init.sql).

CREATE VIEW searchable_figure_refs AS
SELECT r.*, f.document_id
FROM figure_refs r
JOIN figures f   ON f.id = r.figure_id
JOIN documents d ON d.id = f.document_id
WHERE d.searchable;
