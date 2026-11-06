-- 004: an image of every handbook page, rendered and stored at ingestion (P7-47; SPEC UC-07 step 3).
-- pages.image_path is a relative key such as FAA-H-8083-15B/pages/p0012.jpg (files, not in the database),
-- NULL until ingestion/render_pages.py has run for the handbook.
ALTER TABLE pages ADD COLUMN image_path text;

-- Search code reads only searchable_* views (BR-001): pages of a document with an unknown licence,
-- or not fully loaded, are never shown. source_url gives the "open the FAA PDF at this page" link.
CREATE VIEW searchable_pages AS
SELECT p.*, d.title AS handbook, d.source_url
FROM pages p
JOIN documents d ON d.id = p.document_id
WHERE d.searchable;
