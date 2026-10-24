# AI Log — Technical Training Assistant (P7)

One entry per significant delegation to an AI tool. Record what was wrong, even when it was small: a log where nothing was ever wrong is read as a log that was not kept.

## Entry template

### YYYY-MM-DD — short title
- **Who:** team member
- **Tool:** e.g. Claude, Copilot
- **What we asked:**
- **What came back:**
- **What was wrong with it:**
- **How we caught it:** (test, manual check against the handbook, code review, running it…)
- **What we kept / changed:**
- **Commit / PR:**

---

## Entries

### 2026-10-19 — Converting the SRS to SPEC.md
- **Who:**
- **Tool:** Claude
- **What we asked:** Convert the Word SRS to SPEC.md and fix the gaps found against the brief (chunking justification, metrics, generation requirement, open items in UC-04 and UC-07, cross-references).
- **What came back:** A Markdown SPEC with a new section 5, FR-009, decisions for UC-04 A2 and UC-07, and a technology decision table.
- **What was wrong with it:** *(fill in after your review — e.g. a requirement you disagreed with, a decision you changed, a wording that did not match the brief)*
- **How we caught it:**
- **What we kept / changed:**
- **Commit / PR:**

### 2026-10-23 — Repository review, corpus downloader and PDF inspector
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Inspect the repository against the brief and SRS, choose the first handbook, write a verified download script and a PDF inspection script.
- **What came back:** `corpus/handbooks.csv`, `ingestion/download_handbook.py` (size check, %PDF/%%EOF check, SHA-256, licence and retrieval date in a `.meta.json`), `ingestion/inspect_pdf.py`, an extended `.gitignore`, and a README fix.
- **What was wrong with it:** (1) The earlier SPEC conversion (19 Oct entry) wrote a change log saying SPEC.md was tagged `spec-v1`, but no tag existed on GitHub. (2) The same conversion linked README to `docs/SPEC.md`, which did not exist at the time. (3) The README "fix" in this session pointed the links to the repository root, which broke them again once we moved the documents into `docs/`.
- **How we caught it:** Listing the tags on GitHub (`git ls-remote --tags origin`) and following the README links after the move.
- **What we kept / changed:** Created the `spec-v1` tag before any code commit. Corrected the README links to `docs/`. Kept the scripts; they were tested on a small generated PDF before we ran them on the real handbook.
- **Commit / PR:** `P7-1` branch `feature/P7-1-corpus-download`

### 2026-10-23 — Figure extractor and caption-check tooling
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** A caption-first figure extractor (figures, captions, PDF page and printed page, referencing paragraphs, unbound regions) and a tool to draw and score the 20-pair manual check.
- **What came back:** `ingestion/extract_figures.py`, `ingestion/sample_check.py`, `tests/test_extract_figures.py` (6 tests on a generated 3-page PDF: raster figure, vector-only figure, caption without artwork, uncaptioned image, figure-range mentions).
- **What was wrong with it:** (1) Crops were flush against the outer lines (no margin); fixed with 6 pt padding. (2) The tests only covered a simple generated PDF, so the first run on the real handbook bound only 277 of 347 captions, and some crops were clearly wrong in the folder view: Figures 3-5 and 3-6 merged into one image with the text between them (they are 11 pt apart, under the 12 pt merge distance); sideways captions on landscape chart pages (e.g. Figure 1-8) never matched because the code only looked *above* a caption; vector paths drawn larger than their clipping area (e.g. PDF page 39) pulled body text and footers into figures.
- **How we caught it:** Browsing `data/extracted/.../figures` in Explorer (3-6, 3-9, 4-12 contained body text), then drawing the caption and region boxes on the problem pages to see why.
- **What we kept / changed:** Three fixes, each with a test that fails when the fix is removed (checked by temporarily disabling it): never merge pieces across a caption; sideways captions bind to the region on their left; vector paths are cut to their clip rectangle. Result: 334/347 bound. Crops that still contain a body paragraph (8) are flagged `needs_review` for the QA queue instead of tuning thresholds to individual pages.
- **Commit / PR:** `P7-2` branch `feature/P7-2-figure-extraction`

### 2026-10-24 — Recording the 20-pair caption check
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Record the results of our manual 20-pair check and the badly cropped figures we found outside the sample, then commit.
- **What came back:** The judged sample saved as `evaluation/check_sample_FAA-H-8083-15B.csv`, sections 1.2 and 1.3 of EVALUATION.md, and a repair step in `sample_check.py score`.
- **What was wrong with it:** Before recording, Claude noticed that our saved CSV was corrupted: Excel had turned all 20 figure numbers and printed page numbers into dates ("1-20" became "20-Jan", "9-21" became "21-Sep"). Our y/n judgements were not affected. Separately, our own browsing found 5 crops with surrounding text (9-19, 9-20, 9-21, 11-13, 11-2) that the extractor's `needs_review` check had not flagged, so the check is weaker than the report suggested.
- **How we caught it:** Excel: reading the CSV before committing it. Bad crops: looking through the figures folder by hand, not only the random sample.
- **What we kept / changed:** Restored the two columns from `figures.jsonl` (matched on `image_path`, which Excel does not alter) and checked that the score is unchanged. Added the repair to `sample_check.py`. Diagnosed the bad crops (raster images placed partly off the page or clipped; the clipping fix only handled vector drawings) and recorded them as the next extractor fix.
- **Commit / PR:** branch `feature/P7-2-figure-extraction`
