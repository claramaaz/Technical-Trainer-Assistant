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

### 2026-10-27 — P7-4: crops that included surrounding text
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Fix the figure crops that contained body text (9-19, 9-20, 9-21, 11-13, 11-2, 1-15).
- **What came back:** Each image/drawing box is shrunk to where it leaves visible ink on a render of the page with the text removed; a box that runs across a caption is cut at the caption. The `needs_review` rule was relaxed to "at least half of a long paragraph inside the crop". Two new tests. Result: 344/347 bound (was 334), 3 caption-only (was 13).
- **What was wrong with it:** (1) The first idea, reading each image's clip from PyMuPDF, does not work: the reported image rectangles ignore clipping. (2) The ink fix alone did not fix 11-13, because one image covered two figures. (3) Of the 16 crops that changed, 2-4, 6-37 and 7-47 still contained text and 2-4 and 6-37 were not flagged, because the flag required a paragraph to be completely inside the crop. (4) The first version of the test PDF crashed PyMuPDF with a memory error (`malloc(): invalid size`) when filling part of a test image; and the first oversized-image test passed even with the fix removed, so it proved nothing.
- **How we caught it:** Looking at every changed crop on a contact sheet, not only the six we asked about; removing each fix temporarily and checking that its test fails.
- **What we kept / changed:** Built the test image from raw bytes; rewrote the oversized-image test so the hidden part hangs sideways over a text column (now it fails without the fix). Known cost: extraction takes about 6.5 minutes instead of 1.5.
- **Commit / PR:** branch `feature/P7-4-crop-fix`

### 2026-10-28 — P7-5: the 15 figures Clara found after v4
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Fix the figures Clara found wrong by browsing every v4 image: 6-6 and 7-49 missing; caption inside 1-18, 1-19, 5-37, 10-1; 5-38 inside 5-37 and 5-51 inside 5-52; text in 6-5, 6-7, 6-37, 7-47, 1-17; 6-35, 8-5, 6-20 cut off.
- **What came back:** Extractor v5. Two figures side by side, each with its own caption, are never joined; the merge distance went from 12 to 8 pt (the column gap is about 11 pt); an image's box keeps only ink that no other piece covers; the caption is cut out of the box and the saved image's margin stops at the caption; uncaptioned pieces beside or just above/below a figure and short labels at its edge are added to it. 22 tests; 347 of 347 captions bound.
- **What was wrong with it:** (1) The first idea for the side-by-side case (block a merge when a caption sits in the gap) did not work: the captions were below the pictures, not between them. (2) The label rule first took a line of body text ("… [Figure 4-7]") and the axis numbers of the next figure; the chart-and-legend case (9-36) was split. (3) Excluding other images' ink made the run take about 7 s per page (45 minutes per handbook) until it was rewritten as one coverage count per page. (4) A containment test failed on rounding noise (79.99999 vs 80). (5) Three of the new tests passed even with their fix removed. (6) The label fix made 4-9 lose its second panel (two panels 47 pt apart, joined before only through their axis labels); found on the contact sheet of the final run and fixed by adding neighbours a second time after the labels. (7) After Clara ran v5 her figures folder held 691 images: the old v4 folder was still there, and the extractor saved each new image as `1-1_p22.png` because `1-1.png` already existed (the suffix was meant only for a figure number printed twice). Now each run empties figures/ and unbound/ first, and the suffix is decided from the captions; a test runs the extractor twice into one folder.
- **How we caught it:** Clara's own review of the images, not the counts; drawing each problem page with its boxes; contact sheets of every crop that changed (37); timing each stage; removing each fix on purpose and re-running the tests.
- **What we kept / changed:** All fixes kept, each now guarded by a test that fails without it. Labels must be closer to this figure than to any other picture, and prose that mentions a figure is never a label. A 1 pt tolerance on containment.
- **Commit / PR:** branch `feature/P7-4-crop-fix`

### 2026-10-28 (afternoon) — upright sideways figures; 4-11, 7-47, 7-1/7-3
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Should figures be stored upright? Fix 4-11 (cropped) and 7-47 (maybe cropped). All other figures were judged good.
- **What came back:** The 12 sideways figures (landscape charts, caption reading bottom to top) are now saved upright, with the turn recorded as `rotation` in figures.jsonl. Text labels are recognised by their small font (8–9 pt; body text 10–11 pt, headings 12 pt). Ink belongs to the smallest piece covering it, and an image placed partly off the page or across both columns loses every contest. Two captions side by side define a column boundary that no merge crosses. A caption and its figure must overlap by at least 30 % of the narrower one. The saved image's margin stops at other figures as well as at the caption.
- **What was wrong with it:** (1) The first ink rule ("only ink no other piece covers") had cut the sky strip off 7-47, because a huge invisible image also covered it. (2) The first label fix took a 12 pt heading ("Slow-Speed Flight") into 4-11; two attempts based on distance and on the page's middle line broke 4-8, 4-9 and 8-5 instead, until the font size was used. (3) Re-running showed a new error in 7-3 (it took 7-1's panel through a 3 pt strip and a caption overlapping by 2 pt), and then a one-line sliver of 7-3 on the edge of 7-1. (4) Two rules added for 7-3 turned out to change nothing and were removed.
- **How we caught it:** Clara's review of 4-11 and 7-47; before/after contact sheets of the 13 crops that changed; drawing page 163 with its boxes; removing each rule on purpose (every remaining rule now has a test that fails without it).
- **What we kept / changed:** 22 tests. Counts unchanged (347/347, 3 flagged); 13 crops changed since the morning run, each checked.
- **Commit / PR:** branch `feature/P7-4-crop-fix`

### 2026-10-28 (evening) — Chunking: measurement, 200-word cap, chunker
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Measure paragraph and section lengths in FAA-H-8083-15B to choose the chunk size cap (SPEC 5.1), then write the chunker.
- **What came back:** `ingestion/chunk_text.py` (`measure` and `chunk` commands): 1,080 chunks, cap 200 words chosen by us from the measurement (median chunk 138.5 words; 15 paragraphs longer than the cap kept whole), with heading path, chapter, PDF and printed pages and the figures each chunk mentions. SPEC 5.1 updated (v1.1). A test file with one example test and a list of cases for us to write.
- **What was wrong with it:** (1) The first measurement found only 150 sections for 371 pages: it read whole text blocks, but in this PDF a heading often shares a block with the paragraph after it; reading line by line gives 577. (2) The table of contents and the Index were counted as paragraphs (one "paragraph" of 1,866 words). (3) Heading paths leaked across chapters (an Appendix A chunk was labelled with the last heading of chapter 11). (4) The chunker crashed instead of explaining when it found no text. (5) The example test passed even when the paragraph-joining rule was removed, because both halves still landed in the same chunk; it now checks the joined sentence.
- **How we caught it:** Comparing the section count with the size of the handbook; reading the longest paragraphs and a random sample of chunks; checking the heading path of the first and last chunk of every chapter; checking that 99.6 % of the body text ends up in chunks; removing the joining rule on purpose.
- **What we kept / changed:** All fixes kept. Tests: per brief 11.3 we write the chunker tests ourselves from the SPEC rules (one example given). Note: the 22 extractor tests were drafted by Claude from failure cases we found and checked by removing each fix; we reviewed them and can explain each one.
- **Commit / PR:** branch for the chunking ticket

### 2026-10-30 — P7-16: embedding baseline (bge-small-en-v1.5), no database
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Explain, then (after approval) build a database-free baseline: embed the 1,080 chunks with BAAI/bge-small-en-v1.5 and measure Hit@1, Hit@5 and MRR on evaluation/questions.csv.
- **What came back:** `evaluation/baseline_retrieval.py` with `embed` and `evaluate` commands (handbook id and model name are arguments). Vectors are normalized, chunks are embedded from `embed_text` in chunks.jsonl order, saved as `chunk_embeddings_<model>.npy` (in data/, not committed). A chunk is relevant if it cites the expected figure (primary) or covers the expected printed page (secondary); reported separately, with and without BGE's query prefix, with a per-question listing. `sentence-transformers>=3` added to requirements.txt and installed in .venv (6.2.0, torch 2.15 CPU). Results in `evaluation/baseline_results_BAAI_bge-small-en-v1.5.txt`.
- **Results (23 answerable questions, figure rule, with prefix):** Hit@1 0.609, Hit@5 0.783, MRR@5 0.688 (MRR over the full ranking 0.701). Page rule: 0.478 / 0.696 / 0.567. Without the prefix the figure rule gives 0.565 / 0.783 / 0.667. Questions that cannot hit: 0 under the figure rule; 1 under the page rule (Q001: no chunk covers page 1-3). Longest chunk 405 tokens, under the 512 limit.
- **What was wrong with it / limits:** (1) Misses are mostly far down the ranking: Q020 rank 466, Q018 rank 52, Q008 rank 18, Q016 rank 10, Q011 rank 9. (2) The two no-answer questions score 0.585 and 0.648 at best, and the lowest answerable top-1 score is 0.631 (Q018), so a single score threshold would not separate them. (3) With 23 questions one question moves a metric by about 4 points; the prefix difference (0.609 vs 0.565 Hit@1) is one question. (4) This is a text-only proxy for the figure metrics of SPEC 5.3, which are defined on figures judged by people; figure documents are not included. (5) Tests were added afterwards (see the follow-up below). (6) Embedding 1,080 chunks took about 7 minutes on CPU, and the first pip install of torch took over 10 minutes.
- **How we caught it:** Checked that every question's figure is cited by at least one chunk before the run; compared token lengths with the model limit; read the per-question top-1 chunk and heading for each miss.
- **What we kept / changed:** Everything kept. Nothing committed or pushed yet.
- **Commit / PR:** branch `feature/P7-16-embedding-baseline` (not committed)
- **Follow-up (same day): tests and write-up.** Added `tests/test_baseline_retrieval.py` (14 tests for `is_relevant`, `first_hit_rank` and `summarize`, on small made-up chunks and rankings with answers worked out by hand) and a "Baseline v1" section (3.1) in `docs/EVALUATION.md` with the setup, relevance rule, results table, worst misses, no-answer scores and the 23-question caveat. Mutation check: 16 deliberate breaks (5 in `is_relevant`, 4 in `first_hit_rank`, 7 in `summarize`, e.g. rank counted from 0, ranking order ignored, rank 5 excluded from the top 5, MRR divided by hits instead of questions); every one made a test fail, and the file was restored byte for byte afterwards. Problems on the way: (1) my restore step rewrote the file with Windows line endings (8,305 to 8,494 bytes); noticed because `diff` showed every line changed, and fixed by copying the saved original back. (2) In the first draft of the EVALUATION table I filled the "where the answer is" column from an unlabeled list and had Q011's cell wrong (it is Turns > Steep Turns > Unusual Attitude Recovery Protection, pp. 7-56 to 7-58) and Q018's heading cut short; both were checked against chunks.jsonl and corrected. The explanations of why each question missed are our reading of the returned chunks, not tested.

### 2026-10-31 — P7-16: figure documents (SPEC 5.1) vs the chunk baseline
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Plan, then (after approval) build one search document per figure (heading + caption + referencing paragraphs), embed it with the same BGE model, and measure figure-level Hit@1, Hit@5 and MRR on the 23 answerable questions; compare with the chunk baseline (EVALUATION 3.1). Reuse the tested scoring functions. If a figure has no referencing paragraph and its page has chunks with different headings, leave the heading empty. Keep an ablation. Mutation-check the tests. Note the different candidate pools and that the questions were written while viewing each figure.
- **What came back:** `evaluation/figure_retrieval.py` (`embed` and `evaluate`, same arguments as the baseline). Each document carries `figure_mentions = [figure_number]` and `printed_pages`, so `first_hit_rank`, `summarize` and `table` from `baseline_retrieval.py` are used unchanged. Four document variants (full, caption + paragraphs, heading + caption, caption). `tests/test_figure_retrieval.py` (32 tests for `unique_heading`, `heading_for`, `document_text`, `build_documents`). EVALUATION.md section 3.2. Results in `evaluation/figure_results_BAAI_bge-small-en-v1.5.txt`.
- **Results (figure rule, with prefix):** chunks 0.609 / 0.783 / 0.688 (Hit@1 / Hit@5 / MRR@5) → figure documents 0.652 / 0.870 / 0.743. Without the prefix: 0.565 / 0.783 / 0.667 → 0.696 / 0.870 / 0.762. Ablation: caption + referencing paragraphs is the best variant (0.696 / 0.913 / 0.775); adding the heading lowers Hit@1 in both comparisons. Q006 got worse (rank 1 → 107); 8 questions improved.
- **What was wrong with it / limits:** (1) The first heading lookup (whole referencing paragraph found in a chunk) left 104 of 347 figures without a heading; the cause is that in figures.jsonl the heading is often glued to the front of the paragraph. We saw it in the empty-heading count, checked one case (Figure 1-1), and added a second try with the last 100 characters (16 left without). The first full run and embedding used the 104 version and had to be redone. (2) The first mutation run for the mutation script gave "NOT FOUND" for two mutations (the shell turned `\\n` into a newline) and, once, 29 "KILLED" while the test file itself was failing (a test string was 98 characters instead of more than 100); the result was only trusted after the unmutated tests passed. (3) The first test version let two mutations survive (no whitespace squash on the chunk; page-fallback joiner), a third one after the tail change (tail only, without trying the whole paragraph first); each got a test. An `if found: break` I had added turned out to be an equivalent mutation (no test could fail) and was removed. (4) First `embed` was started with the system Python (no sentence-transformers); the project's .venv was needed. (5) 2 documents are over the 512-token limit and are cut off. (6) Not like-for-like with 3.1: 347 figures vs 1,080 chunks, and the questions were written while looking at each figure's caption and paragraph, which may favour figure documents; both are written in 3.2. With 23 questions all differences are one to three questions.
- **How we caught it:** Counting figures without a heading; printing the first referencing paragraph of a figure without a heading; comparing per-question ranks with the chunk baseline; mutation check of the new functions: 29 deliberate breaks (4 in `unique_heading`, 12 in `heading_for`, 6 in `document_text`, 7 in `build_documents`), every one made a test fail in the final run; the script restored `figure_retrieval.py` and `cmp` showed it identical to the saved copy.
- **What we kept / changed:** Everything kept, as the SPEC 5.1 composition (full document) is the reported main row, with the ablation next to it. No decision yet on whether to drop the heading. Nothing committed.
- **Commit / PR:** branch `feature/P7-16-figure-documents` (not committed)

### 2026-10-31 — P7-20: thin end-to-end search slice (API + one page), no database
- **Who:** Clara
- **Tool:** Claude
- **What we asked:** Plan, then (after approval) build a thin search slice on the existing files of FAA-H-8083-15B and the baseline v2 figure documents: `retrieve(query, k)` with a no-answer rule, a FastAPI app (`/search`, `/figures/{id}/image`, `/health`), one plain HTML+JS page, tests with a mutation check. All data access behind one function so the pgvector work can replace it. The page must show the text "No adequate answer found in the handbook" clearly and nothing else in that case.
- **What came back (each file in plain English):**
  - `backend/retrieval.py`: `load_index()` is the only function that reads files (figures, chunks, the saved embeddings, the handbook name); `retrieve()` turns the question into a vector with the same model and query prefix as the evaluation, takes the k closest figure documents by dot product, and returns them, or returns no results with the reason `no_adequate_answer` when the best score is under `THRESHOLD`. It imports `build_documents`, `load_jsonl`, `paths`, `QUERY_PREFIX` and `load_model` from `evaluation/`, so the document text is the one that was evaluated; `evaluation/` is unchanged.
  - `backend/app.py`: FastAPI. `/health` says ok; `/search?q=` (q required, not blank, at most 500 characters; optional k 1 to 20) returns what `retrieve` returns; `/figures/{id}/image` sends the PNG of a figure, taking the file path from the index and never from the URL; `/` serves the page.
  - `frontend/index.html`: search box and result cards (image, caption, passage, "Instrument Flying Handbook, page 3-4"); on a narrow phone screen it is one column. When the answer is "no adequate answer" it shows only a red box with the text "No adequate answer found in the handbook". Handbook text is inserted as text, never as HTML.
  - `tests/conftest.py`, `tests/test_retrieval.py`, `tests/test_app.py`: 24 tests (see below). `requirements.txt`: `fastapi` (the web framework that defines the endpoints), `uvicorn` (the server that runs it), `httpx` (the HTTP client FastAPI's test client needs, so tests call the API without a server).
- **THRESHOLD = 0.65 is NOT validated.** It was chosen by reading the scores of the same 23 answerable and 2 no-answer questions (Q001 to Q025) that the tests then check, so the tests passing says nothing about how it works on new questions. It rests on two no-answer questions (best scores 0.580 and 0.626) and the margins are tiny: the lowest correct top-1 score is 0.653 (Q017), 0.003 above the line, and Q018 (0.605, already a miss at rank 8) is below it. Wrong top-1 results score high too (Q006 0.748, Q020 0.767), so a threshold cannot catch wrong answers. It must be re-set on a separate question set with many more no-answer questions. The constant is marked provisional in the code and tested only at its boundary, not as a quality claim.
- **Tests:** 3 known questions return the expected figure first with the right printed page, handbook and caption (Q003 to 3-9, Q021 to 5-40, Q019 to 11-18, chosen for margin: top-1 score 0.84 to 0.91); the two no-answer questions return empty results with the reason; boundary tests on a made-up index (just under the threshold rejected, equal accepted; best-first order; k respected; the decision uses the best score); API status codes (200 health, search and image; 422 for missing, empty or blank q and k = 0; 404 for unknown and traversal-style ids; 200 with the reason for a no-answer question; the page contains the no-answer text). Last full run before adding the 24th test: 23 passed in about 4 minutes (most of it loading torch and the model; the data-only tests take seconds).
- **Mutation check (9 deliberate one-line breaks, each followed by a byte-for-byte restore check):** killed: threshold `<` to `<=`; `<` to `>`; threshold applied to the last of the top k instead of the best; ranking ascending; k ignored; unknown image id no longer a 404; blank q accepted; printed page replaced by the PDF page. **One survived the first time:** building the image path from the URL id instead of the index. The traversal tests did not catch it because the route does not accept "/" and ".png" is appended, so no file is found anyway; the check only matters for a file that exists on disk but is not in the index. We added a test for exactly that case (3-9 removed from the index while figures/3-9.png exists) and the same mutation is now killed. A tenth idea (passage from the last instead of the first referencing paragraph) was not tested: no test checks the passage text.
- **What was wrong with it / limits:** (1) My first attempt to write the files with shell here-documents failed with a quoting error and wrote nothing; I used the file-writing tool instead. (2) The first draft of the mutation script passed two `-k` filters to pytest, of which only the last counts; fixed before the run. (3) No test checks the passage text or the six figures with no referencing paragraph (empty passage; the page then shows the caption and source only). (4) The first request loads the model and the data (several seconds), later ones are fast. (5) The page was not opened in a browser or on a phone yet; only the API and the served HTML text were tested. (6) SPEC 2.5 says React for the frontend; this slice is plain HTML+JS as asked, and the SPEC is not changed. (7) The image endpoint serves PNGs in full size; the thumbnails of NFR-001 are not done.
- **How we caught it:** Reading the scores of the earlier evaluation before choosing the threshold (which also showed how thin the margin is); the mutation check found the weak image test.
- **What we kept / changed:** Everything kept. Nothing committed or pushed.
- **Commit / PR:** branch `feature/P7-20-search-api` (not committed)
