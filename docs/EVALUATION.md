# EVALUATION — Technical Training Assistant (P7)

Every number here is produced by a command listed next to it, so anyone can reproduce it.
Metric definitions are in [SPEC.md §5.3](SPEC.md#53-evaluation-metrics).

## 1. Ingestion of the first handbook (Week 1 gate)

**Handbook:** FAA-H-8083-15B, Instrument Flying Handbook
**Source URL:** https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/FAA-H-8083-15B.pdf
**Licence:** United States Government work, public domain
**Retrieved:** 2026-10-24T05:56:35Z by `ingestion/download_handbook.py`
**File size / SHA-256:** 68,414,993 bytes (identical to the size in the project brief) / `15cbf13fef6bf9810ad38d1f5bbff318133554a6ca118c4474bc1760ad9059d5`

### 1.1 Extraction counts

Command: `python ingestion/extract_figures.py data/raw/FAA-H-8083-15B.pdf`
(the counts below come from `data/extracted/FAA-H-8083-15B/report.json`, extractor v6)

| Count | Value |
| --- | --- |
| PDF pages | 371 |
| Captions found ("Figure X-Y.") | 347 |
| Figures bound to a caption | 347 (100 %) |
| Captions with no figure region (sent to QA) | 0 |
| Unbound graphic regions (sent to QA) | 31 |
| Bound figures flagged `needs_review` (crop contains a body paragraph) | 3 |
| Figures with at least one referencing paragraph | 341 |
| Figures missing a printed page number | 0 |

The v3 and v4 counts were obtained identically on two machines (Windows laptop and a Linux environment) from the same PDF (same SHA-256); re-run v5 on the laptop to confirm.

Captions per chapter: 1: 24, 2: 16, 3: 9, 4: 23, 5: 60, 6: 39, 7: 75, 8: 20, 9: 43, 10: 20, 11: 18.

**Extractor iterations on this handbook** (same PDF, same caption detector):

| Version | Bound | Caption only | Unbound regions | Change |
| --- | --- | --- | --- | --- |
| v1 | 277 | 70 | 72 | first run |
| v2 | 298 | 49 | 61 | no merge across a caption; sideways captions bind to the left |
| v3 | 334 | 13 | 35 | vector paths cut to their clipping area; caption overlapping the bottom of its artwork accepted |
| v4 | 344 | 3 | 33 | every image/drawing box shrunk to its visible ink on a text-free render; a box that runs across a caption is cut there (P7-4) |
| v5 | 347 | 0 | 31 | side-by-side figures with their own captions kept apart; merge distance 12 → 8 pt (below the ~11 pt column gap); an image keeps only ink no other piece covers; caption cut out of the box and the image margin stops at the caption; pieces beside / just above or below a figure and short labels at its edge added (P7-5) |
| v6 | 347 | 0 | 31 | same counts, 13 crops corrected: 12 sideways figures saved upright; labels recognised by their small font; ink goes to the smallest piece over it (off-page / cross-column images lose); a column boundary between side-by-side captions; caption and figure must overlap ≥ 30 %; image margin stops at other figures |

Every figure bound in an earlier version is still bound in the next. Run time: about 1.5 minutes (v3), 6.5 (v4, each page is rendered once more without text), 5.5 (v5, after removing pieces that lie inside other pieces before merging).

Caption-only figures (v6): none.
Flagged for review (v6): 5-7, 6-33, 10-10. The flag fires when at least half of a long paragraph lies inside the crop.

**Visual review of v5:** every one of the 37 crops that changed from v4 was looked at on a contact sheet, plus the 15 figures Clara reported after v4. One regression found in that review (4-9 lost its second panel) was fixed before the final run.

**Visual review of v6:** Clara judged all v5 figures good except 4-11 (axis titles cut) and 7-47 (sky strip cut). The 13 crops that changed in v6 were compared before/after; 7-3 regressed during the work (took 7-1's panel) and was fixed. The 12 sideways figures (1-8, 1-9, 1-11, 1-12, 1-16, 1-18 to 1-22, 1-24, 10-18) are saved upright.

**Comparison with the figure list in the handbook** (the brief asks for this). The handbook has no List of Figures (its front matter has only a table of contents), so completeness was checked another way. (1) Figures are numbered in sequence within each chapter; for each of the 11 chapters the extracted numbers are exactly 1..max with no gap (24, 16, 9, 23, 60, 39, 75, 20, 43, 20, 18 = 347). (2) An independent count of every text block in the PDF starting "Figure N-N." finds 347 captions, none missing from figures.jsonl. No "Figure A-1"-style captions exist. Limit: this covers captioned figures only; uncaptioned graphics are the 31 unbound regions in the QA queue.

### 1.2 Manual check of figure–caption pairs

Command: `python ingestion/sample_check.py draw FAA-H-8083-15B --n 20 --seed 7`, then judged by hand against the PDF, then `... score FAA-H-8083-15B`.
Judged sample committed as [`evaluation/check_sample_FAA-H-8083-15B.csv`](../evaluation/check_sample_FAA-H-8083-15B.csv).

| Measure | Result |
| --- | --- |
| Sample size / seed | 20 / 7, drawn from the 334 bound figures (extractor v3) |
| Caption-binding accuracy (caption_correct) | **20/20 = 100 %** |
| Printed-page correctness (page_correct) | **20/20 = 100 %** |
| Figure image complete (image_complete) | **16/20 = 80 %** |
| Judged by / date | Clara, 2026-10-24 |

Incomplete images in the sample: 5-39 and 9-21 (caption included in the image), 9-6 and 10-2 (part of the surrounding text included). No caption was bound to the wrong image. These judgements are for extractor v3; the four incomplete images were fixed in v4 (see 1.3) and should be re-judged against v4.

With 20 pairs, 20/20 is consistent with a true caption-binding accuracy anywhere from about 84 % to 100 % (95 % Wilson interval); a larger sample would narrow this.

**Re-check on the final extractor (v6), 50 pairs (14 Nov).** Command: `python ingestion/sample_check.py draw FAA-H-8083-15B --n 50 --seed 11`, judged by hand against the PDF, then `... score FAA-H-8083-15B`. Judged sample committed as [`evaluation/check_sample_FAA-H-8083-15B_v6_n50.csv`](../evaluation/check_sample_FAA-H-8083-15B_v6_n50.csv).

| Measure | Result |
| --- | --- |
| Sample size / seed | 50 / 11, drawn from the 347 bound figures (extractor v6) |
| Caption-binding accuracy (caption_correct) | **50/50 = 100 %** |
| Printed-page correctness (page_correct) | **50/50 = 100 %** |
| Figure image complete (image_complete) | **50/50 = 100 %** |
| Judged by / date | Clara, 2026-11-14 |

With 50 pairs, 50/50 is consistent with a true accuracy of about 93 % to 100 % (95 % Wilson interval). The sample covers bound figures only, not the 31 unbound regions. It replaces the v3 sample above as the caption-binding figure for 15B; the 25C half (50 pairs, same seed) is judged by Mia.

### 1.3 Errors and limitations observed

| Error type | Examples | Cause | Status |
| --- | --- | --- | --- |
| Crop includes surrounding body text | 9-6, 10-2 (sample); 9-19, 9-20, 9-21, 11-13, 11-2 (found while browsing, outside the sample); 1-15 | Raster images placed partly off the page or larger than their visible area (e.g. PDF page 263: an image spans x = 189 to 693 on a 594 pt wide page). The PDF crops them, but the extractor uses the full image rectangle. The v3 clipping fix covers vector drawings only, not images. The labels inside these crops are short, so the `needs_review` check (paragraph > 250 characters) did not flag them. | **Fixed in v4 (P7-4):** boxes are shrunk to their visible ink. 9-19, 9-20, 9-21, 11-13, 11-2, 1-15, 9-6 and 10-2 checked by eye after the fix: no body text left. |
| Caption included in the image | 5-39, 9-21 | The caption overlaps the bottom of the artwork region, so the crop includes it | **Fixed in v4:** 5-39 checked by eye, caption no longer in the image. |
| Caption found but no figure region | v3: 13 figures; v4: 3 (6-6, 7-1, 7-49); v5: 0 | Mostly one oversized image covering two figures, so one caption took the whole box and the other found nothing. v4 cuts such a box at the caption. | 3 left for the QA queue |
| Crop still contains body text | v4: 2-4, 6-37, 7-47 | Figure and text are interleaved in ways a rectangle cannot separate | v5: 3 left (5-7, 6-33, 10-10), flagged `needs_review` for the QA queue |
| Found by Clara after v4 (28 Oct): 6-6 and 7-49 missing; caption inside 1-18, 1-19, 5-37, 10-1; 5-38 inside 5-37, 5-51 inside 5-52; text in 6-5, 6-7, 6-37, 7-47, 1-17; 6-35, 8-5, 6-20 cut off | 15 figures | Side-by-side figures joined across the ~11 pt column gap; an oversized image keeping other figures' ink; the 6 pt image margin reaching into the caption; labels and separate side pieces left outside the box | **Fixed in v5 (P7-5)**, each case checked by eye on its page |
| Excel converted figure numbers to dates while judging ("1-20" became "20-Jan") | all 20 rows | Excel's automatic date detection when opening a CSV | Fixed: `sample_check.py score` restores both columns from `figures.jsonl`. The committed evidence file has the restored values; the y/n judgements are unchanged. |

### 1.4 Second handbook: FAA-H-8083-25C, Pilot's Handbook of Aeronautical Knowledge (P7-18)

**Source chain:** the official index (https://www.faa.gov/regulations_policies/handbooks_manuals/aviation) lists no `.pdf` named `faa-h-8083-25c.pdf`; it links "Pilot's Handbook of Aeronautical Knowledge (FAA-H-8083-25C)" to the PHAK page (https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak). That page links "Pilot's Handbook of Aeronautical Knowledge, FAA-H-8083-25C (Full Version)" to `/regulations_policies/handbooks_manuals/aviation/faa-h-8083-25c.pdf`, with no redirect. So: index → PHAK page → PDF. The chain is recorded in the `source_note` column of `corpus/handbooks.csv`.
**Source URL:** https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/faa-h-8083-25c.pdf
**Licence:** United States Government work, public domain
**Retrieved:** 2026-11-04T19:05:30Z by `ingestion/download_handbook.py` (HEAD before download: HTTP 200, `application/pdf`, Last-Modified 17 Jul 2023)
**File size / SHA-256:** 77,598,564 bytes (equal to the HEAD Content-Length) / `247929cace0ab56b376e683eba540cc4c8f39f199ab35414e8b604e24f395cb7`

Commands: `python ingestion/inspect_pdf.py data/raw/FAA-H-8083-25C.pdf`, `python ingestion/extract_figures.py data/raw/FAA-H-8083-25C.pdf`, `python ingestion/chunk_text.py chunk data/raw/FAA-H-8083-25C.pdf`. Nothing is loaded into the database yet.

**Counts before and after the extractor fix** (from `data/extracted/FAA-H-8083-25C/report.json`):

| | First run (before the fix) | Fix, first attempt | Final |
| --- | --- | --- | --- |
| PDF pages | 522 | 522 | 522 |
| Captions found | 494 | 502 | **502** |
| Bound to a caption | 494 | 501 | **502 (100 %)** |
| Captions with no figure region | 0 | 1 (17-23) | **0** |
| Unbound graphic regions | 45 | 44 | **42** |
| Flagged `needs_review` | 31 | 32 | **32** (30 "crop contains a body paragraph", 2 "caption number does not match the chapter of the printed page") |
| Figures with at least one referencing paragraph | 490 | | 498 |
| Text chunks | 1,740 | | 1,739 |

Captions per chapter after the fix: 1: 25, 2: 24, 3: 22, 4: 8, 5: 71, 6: 25, 7: 49, 8: 39, 9: 10, 10: 12, 11: 33, 12: 29, 13: 21, 14: 60, 15: 9, 16: 40, 17: 25 (502, with 6-48 counted under chapter 6 and 10-31 under chapter 10 as printed).

**What the fix was.** In 25C, 8 pairs of side-by-side figures have their two captions stored as ONE text block (PDF pages 17, 33, 103, 123, 165, 233, 338, 450). The extractor read the block as one caption and lost the second figure: 1-1, 1-22, 5-8, 5-40, 7-8, 9-4, 14-2, 17-24. `text_blocks()` now cuts such a block into one piece per line that starts with "Figure N-M."; a wrapped second line joins the caption that starts nearest to it on the left. Result: all 8 figures are bound, and each caption is bound to its own image (looked at on contact sheets, e.g. 1-1 Leonardo's drawing and 1-2 the Cayley glider; before the fix 1-2 was bound to Leonardo's drawing, i.e. the pair was wrong, not only incomplete).

**A regression found and fixed on the way.** With separate captions the extractor drew a boundary halfway between them, and the boundary cut anything it crossed. Because the 25C captions are much narrower than their figures, it cut the full-width Figure 17-23 (left without an image, 17-23 became "caption only") and the right side of 17-24, 9-2, 9-1 and 5-38. Fix: the boundary applies only below the lowest body-text paragraph it crosses, and a box is cut at the boundary only when it reaches over by at most 16 pt (the 3 pt strip it was made for, 7-1 / 7-3 in 15B); a wider figure is kept whole, and merging across the line stays blocked. The same change repaired 15 figures that the first 25C run had cropped too narrow (1-3, 5-23, 5-35, 5-36, 5-47, 5-56, 5-57, 6-1, 6-2, 6-8, 6-17, 10-2, 14-6, 14-7, 16-35; 5-35 had lost two of its three panels to the unbound list). Tests added: `tests/test_extract_figures.py` (one block with two captions gives two figures with the right numbers and texts; the boundary does not cut wide figures; the chapter-mismatch flag). The new tests fail on the code before the fix. **FAA-H-8083-15B is unchanged:** `figures.jsonl` is byte-identical before and after (347 captions, 347 bound, the same 3 flags 5-7, 6-33, 10-10, the same 31 unbound regions, same report). The 15B PNG files were not compared byte by byte (no copy of the old ones was kept); their boxes in `figures.jsonl` are identical and the drawing code did not change.

**Comparison with the handbook's list of figures.** This PDF has **no List of Figures** (front matter: preface, contributors, a chapter and section table of contents), so the comparison used the body text instead: (1) for each chapter, the figure numbers extracted from captions, compared with 1..highest number; (2) every "Figure X-Y" mentioned anywhere in the text, compared with the captions. After the fix, every captioned figure is mentioned in the text, and the only mentioned numbers without a caption under that number are the four below. The inspector's own "numbering gaps" line (`inspect_pdf.py`) reads captions block by block, so its count (494) still lacks the 8 figures above; it was not changed, and its long gaps (ch. 6: 25 to 47, ch. 10: 12 to 30) are not missing figures (see 1.4 errors).

**Errors in the handbook itself (the extractor is right):**

| What | Where | Detail | Handling |
| --- | --- | --- | --- |
| Caption "Figure 6-48" is printed in chapter 7 | PDF page 200, printed page 7-40 | The text calls it "Figure 7-48" (deicing boots) | Number kept as printed; `needs_review`: "caption number does not match the chapter of the printed page" |
| Caption "Figure 10-31" is printed in chapter 11 | PDF page 282, printed page 11-26 | The text calls it "Figure 11-31" (crosswind component chart) | Same |
| Text refers to "Figure 4-51" | PDF page 137 | No such figure; the next caption on the page is 5-60 (probably meant) | Not a figure; stays unmatched |
| Text refers to "Figure 10-32" | PDF page 282 | No such figure; chapter 11 has 11-32, a landing distance table (probably meant) | Not a figure; stays unmatched |

Because of the two mis-printed captions, 6-48, 10-31, 11-32 and 10-8 have no referencing paragraph (498 of 502 have one); 6-48, 10-31 and 11-32 are explained by the wrong numbers in the text, 10-8 ("CG moment envelope", PDF page 252) was not examined.

**Chapters and appendices.** The chunker takes a chunk's chapter from the prefix of the printed page number ("4-8" gives chapter 4, "G-7" gives G). This PDF has parts A (Appendix A, 8 pages of performance charts), B (Appendix B, abbreviations and acronyms, 12 pages), C (Appendix C, airport signs, 4 pages), G (Glossary, 36 pages) and I (Index, 10 pages, skipped on purpose). Chunks exist only for B and G because A and C have almost no running text (A: chart titles only; C: a figure and sign tables), so the chunker found no paragraph there. The chapter of every one of the 1,740 chunks (first run) agrees with the printed pages it covers (0 mismatches), and the chapter of every figure agrees with its printed page except the two mis-printed captions above. `PART_NAMES` in `chunk_text.py` has no entry for "C" (it would give the heading `None` if C ever had a chunk).

**Limitations found, not fixed:**
- **Figures with a lettered number are not captured.** The caption pattern is `Figure <digits>-<digits>.`; Appendix C has "Figure C-1", "C-2", "C-3" (PDF pages 473, 474, 476), which are therefore not figures in the output. Appendix A's 8 chart pages have no "Figure" caption at all and sit in the unbound list. 15B has no lettered captions, so the pattern never failed before.
- 30 figures are flagged "crop contains a body paragraph" and need a look in the QA queue (3 in 15B).
- The 42 unbound regions were not looked at one by one: they are mostly front matter (pages 1 to 6), the Appendix A and C pages, the glossary and the index.
- **Manual sample check (5 Nov):** `evaluation/check_sample_FAA-H-8083-25C.csv` (20 pairs, seed 7, drawn from the 502 bound figures, same format as the 15B file). Result: **caption correct 20/20, page correct 20/20, image complete 20/20.** Method: Claude did an AI pre-check (looked at all 20 images against their captions, and checked by script that each caption and its printed page are on the stated PDF page), and Clara confirmed it. The sample is small (20 of 502), so 20/20 does not prove a zero error rate; it is a spot check. It does not cover the 30 "body paragraph" flags or the 42 unbound regions. Claude had also looked at contact sheets of the 8 recovered figures and the 15 repaired ones.
- Run time: the last 25C extraction took roughly 40 minutes on this PC (the 15B run was going at the same time for part of it); 15B alone took 5.5 minutes in v5 (see 1.1).

## 2. Evaluation set (Week 3)
*(50+ questions, each with the expected figure identified by handbook and printed page)*

**Content.** 50 questions in `evaluation/questions.csv`: Q001-Q025 written by Clara for FAA-H-8083-15B, Q026-Q050 written by Mia for FAA-H-8083-25C. Each answerable question names the expected figure by handbook, figure number and printed page.

| Type | Count | Meaning |
| --- | --- | --- |
| topic | 30 | a technical topic named in the question |
| symptom | 12 | a problem described without the technical names |
| no-answer | 8 | the corpus has no answer (tests FR-002, UC-02 A1) |

42 questions are answerable, 8 are not.

**Commit dates (brief section 8).** Q001-Q025: 2026-10-28 (commit 2b09bb4). Q026-Q050: 2026-11-07 (commit 0256e4f). Both before the final fortnight.

**Check that the expected figures exist.** `python evaluation/check_questions_in_db.py` looks up every answerable question's (handbook, figure number) in the database and compares the printed page. Result on 2026-11-07: 42 checked, 0 figures missing, 0 printed pages different. This proves the set contains no typo in its references; it does not prove that the figure answers the question (that is the human judgement, 3.5).

## 3. Baseline retrieval results (Week 3)

### 3.1 Baseline v1: text chunks only, BAAI/bge-small-en-v1.5, no database

Commands (from the repository root; the second step reads `chunk_embeddings_*.npy` written by the first):
`python evaluation/baseline_retrieval.py embed FAA-H-8083-15B BAAI/bge-small-en-v1.5`
`python evaluation/baseline_retrieval.py evaluate FAA-H-8083-15B BAAI/bge-small-en-v1.5`
Full output: [`evaluation/baseline_results_BAAI_bge-small-en-v1.5.txt`](../evaluation/baseline_results_BAAI_bge-small-en-v1.5.txt). The scoring functions are covered by `tests/test_baseline_retrieval.py`.

**Setup.** Model `BAAI/bge-small-en-v1.5` (384 dimensions; sentence-transformers 6.2.0). The 1,080 chunks of `chunks.jsonl` (5.1, cap 200 words) are embedded from `embed_text` (heading path + text), in file order, with normalized vectors; ranking is cosine similarity, which for normalized vectors is a dot product, over all 1,080 chunks. The longest chunk is 405 tokens, under the model's 512-token limit, so nothing is truncated. Questions are encoded with BGE's query instruction ("Represent this sentence for searching relevant passages: "); chunks have no prefix. Figures are not searched in this baseline (no figure documents, no image embeddings).

**Relevance rule.** A chunk is relevant to a question when its `figure_mentions` contains the question's expected figure (primary: the paragraph that cites a figure is the text that explains it). A secondary, looser rule counts a chunk whose `printed_pages` contains the question's expected printed page. The rules are reported separately. This is a text-only proxy for the figure metrics of 5.3, which are defined on figures judged by people (scores 2/1/0); it does not replace that judgement.

**Questions.** `evaluation/questions.csv`, Clara's Q001 to Q025: 23 answerable (20 topic, 3 symptom) and 2 no-answer. Hit@1, Hit@5 and MRR are averaged over the 23 answerable questions; the no-answer questions are not scored here. MRR@5 is 0 for a question whose first relevant chunk is not in the top 5 (as in 5.3); "MRR full" uses the whole ranking.

**Questions that cannot hit:** none under the figure rule (every expected figure is cited by at least one chunk); one under the page rule (Q001: no chunk covers printed page 1-3).

| Relevance rule | Query prefix | Hit@1 | Hit@5 | MRR@5 | MRR full |
| --- | --- | --- | --- | --- | --- |
| **Figure (primary)** | **with** | **0.609** (14/23) | **0.783** (18/23) | **0.688** | 0.701 |
| Figure | without | 0.565 (13/23) | 0.783 (18/23) | 0.667 | 0.676 |
| Page (secondary) | with | 0.478 (11/23) | 0.696 (16/23) | 0.567 | 0.586 |
| Page | without | 0.522 (12/23) | 0.652 (15/23) | 0.576 | 0.599 |

By type (figure rule, with prefix): topic (20) Hit@1 0.600, Hit@5 0.800, MRR@5 0.692; symptom (3) Hit@1 0.667, Hit@5 0.667, MRR@5 0.667. With 3 symptom questions these two lines say very little.

**Worst misses** (figure rule, with prefix; the five questions with no relevant chunk in the top 5):

| Question | Expected figure | Rank of first relevant chunk | Top-1 chunk returned | Where the answer is |
| --- | --- | --- | --- | --- |
| Q020 "During a climb the pilot notices the airspeed indicator is reading zero. What could be the cause?" (symptom) | 5-2 | **466** of 1,080 | Learning Methods > Supporting Method > Pitch Control (p. 6-6; top-1 score 0.773) | Pitot/Static Systems > Static Pressure |
| Q018 "What the pilot utilized to determine which airport best suits to their individual needs?" | 11-11 | 52 | Terminal Arrival Area (TAA) > Airport Sketch / Airport Diagram (p. 1-27) | GPS Nearest Airport Function > Nearest Airports Using the MFD > Nearest Airports Page Soft Keys (p. 11-10) |
| Q008 "What do pilots do under extremely cold conditions?" | 5-7 | 18 | "Summary" (p. 4-17) | Pitot/Static Instruments > Sensitive Altimeter > Cold Weather Altimeter Errors |
| Q016 "How does wind affect an aircraft during takeoff and landing?" | 10-17 | 10 | Slow-Speed Flight > Small Airplanes (p. 4-10) | Instrument Weather Flying > Weather Conditions > Wind Shear (p. 10-25) |
| Q011 "What warnings appear on the PFD if the AHRS fails during flight?" | 7-73 | 9 | Aircraft System Malfunctions > Electronic Flight Display Malfunction (p. 11-4) | Turns > Steep Turns > Unusual Attitude Recovery Protection (pp. 7-56 to 7-58) |

Reading of the misses (our interpretation from reading the returned chunks, not tested): Q020 is the clearest case of the learner's symptom wording ("airspeed indicator reading zero") sharing few words with the handbook's wording (static and pitot pressure); the model returned a chunk about pitch control instead. Q018, Q008 and Q016 are written in general terms ("which airport best suits", "extremely cold conditions", "wind ... during takeoff and landing") and the model returned a chunk on a nearby but different topic. For Q011 the returned chunk (display malfunctions, chapter 11) is related, but the expected chunk is in chapter 7, in the discussion of unusual attitude recovery protection. Whether a different model, a hybrid with keyword search, or the figure documents of 5.1 would fix these is not yet measured.

**No-answer questions.** The best cosine score over all chunks is 0.585 for Q024 ("maximum passenger capacity of a Boeing 747") and 0.648 for Q025 ("reset the flight computer on an Airbus A320"). Among the 14 questions whose top-1 chunk is relevant, the lowest top-1 score is 0.750 (Q002). *Hypothesis only:* a score threshold between 0.648 and 0.750 would answer "no answer found" for both no-answer questions and keep all 14 correct top-1 results. This rests on two no-answer questions and is not evidence that such a threshold works: wrong top-1 chunks also score high (Q020 0.773, Q011 0.768, Q008 0.742), so a threshold cannot catch wrong answers, and it has not been tested on more no-answer questions.

**Caveat on sample size.** The baseline uses 23 answerable questions, all written by one author; one question moves each metric by about 4 percentage points (1/23 = 0.043). The difference between the with and without prefix Hit@1 (0.609 vs 0.565) is one question. The 95 % intervals are wide (for example Hit@5 = 18/23 is consistent with a true value of 0.58 to 0.90 (Wilson)), so treat these numbers as a first reading, to be repeated on the full 50+ question set (Mia's Q026 to Q050 are not yet included).

### 3.2 Figure documents, BAAI/bge-small-en-v1.5, no database

Commands (from the repository root; `embed` writes one `figure_embeddings_<variant>_<model>.npy` per variant, `evaluate` reads them):
`python evaluation/figure_retrieval.py embed FAA-H-8083-15B BAAI/bge-small-en-v1.5`
`python evaluation/figure_retrieval.py evaluate FAA-H-8083-15B BAAI/bge-small-en-v1.5`
Full output: [`evaluation/figure_results_BAAI_bge-small-en-v1.5.txt`](../evaluation/figure_results_BAAI_bge-small-en-v1.5.txt). The new functions (`heading_for`, `unique_heading`, `document_text`, `build_documents`) are covered by `tests/test_figure_retrieval.py`; the scoring functions are the ones of 3.1 (`first_hit_rank`, `summarize`, `table`), unchanged.

**Setup (SPEC 5.1, figure documents).** One search document per figure of `figures.jsonl` (347): section heading, caption, then the paragraphs that reference the figure, one per line. Same model, same normalized vectors, same 23 answerable questions and same query prefix as 3.1. A figure is a hit when its `figure_number` is the question's expected figure; the rank is the position of that figure among the 347. This is again a proxy for the figure metrics of 5.3 (no human judgement of "related" figures, score 1).

**Where the heading comes from.** `figures.jsonl` does not store it. It is taken from `chunks.jsonl`: the heading of the chunks that contain the figure's first referencing paragraph; if that paragraph is in no chunk, the heading of the chunks that contain its last 100 characters (the extracted paragraphs often have the heading text glued to their front, e.g. "Airspace Classification Airspace in the United States …", which the chunker had split off; matching only the whole paragraph left 104 figures without a heading, matching its end leaves 16). If those chunks have different headings, or the figure has no referencing paragraph, the heading of the chunks covering the figure's printed page, but only when they all share the same heading; otherwise the heading is left **empty** (no guessing). Result: 6 figures have no referencing paragraph and 16 have no heading (10 of them have referencing paragraphs). The first reference alone decides the heading, even when a figure is cited from several sections.

**Questions that cannot hit:** none (all 23 expected figures are in `figures.jsonl`). Documents longer than the model limit: 2 of 347 (longest 536 tokens, limit 512); their last words are cut off.

**Result** (figure rule, 23 answerable questions; the chunk rows are copied from 3.1):

| Index | Query prefix | Hit@1 | Hit@5 | MRR@5 | MRR full |
| --- | --- | --- | --- | --- | --- |
| Chunks (1,080) | with | 0.609 (14/23) | 0.783 (18/23) | 0.688 | 0.701 |
| **Figure documents (347)** | **with** | **0.652** (15/23) | **0.870** (20/23) | **0.743** | 0.749 |
| Chunks (1,080) | without | 0.565 (13/23) | 0.783 (18/23) | 0.667 | 0.676 |
| Figure documents (347) | without | 0.696 (16/23) | 0.870 (20/23) | 0.762 | 0.765 |

By type (figure documents, with prefix): topic (20) Hit@1 0.650, Hit@5 0.900, MRR@5 0.754; symptom (3) Hit@1 0.667, Hit@5 0.667, MRR@5 0.667. As in 3.1, three symptom questions say very little.

**Question by question** (rank of the expected figure; chunk rank from 3.1). Better with figure documents: Q008 18 → 1, Q011 9 → 4, Q016 10 → 2, Q017 2 → 1, Q018 52 → 8, Q020 466 → 62, Q021 2 → 1, Q014 3 → 2. Worse: Q006 1 → 107 and Q015 1 → 3. The other 13 are the same. Still outside the top 5: Q006 (107), Q020 (62), Q018 (8). Q006 ("How does temperature change with altitude …", expected 4-7 "Koch chart sample") is the one real loss: the figure's only referencing paragraph is a fragment ("a Koch Chart or a flight computer with a density altitude function. [Figure 4-7]") and its caption shares no word with the question, whereas the chunk citing it is about the atmosphere and density altitude. This is our reading of the texts, not tested.

**What goes into the document** (ablation, with prefix; same questions):

| Document text | Hit@1 | Hit@5 | MRR@5 | MRR full |
| --- | --- | --- | --- | --- |
| Caption only | 0.609 (14/23) | 0.783 (18/23) | 0.651 | 0.660 |
| Heading + caption | 0.478 (11/23) | 0.870 (20/23) | 0.619 | 0.620 |
| Caption + referencing paragraphs | 0.696 (16/23) | 0.913 (21/23) | 0.775 | 0.776 |
| **Heading + caption + paragraphs (SPEC 5.1)** | 0.652 (15/23) | 0.870 (20/23) | 0.743 | 0.749 |

Without the prefix (Hit@1 / Hit@5: caption 0.609 / 0.783, heading + caption 0.522 / 0.783, caption + paragraphs 0.652 / 0.913, full 0.696 / 0.870) the full document and caption + paragraphs swap places on Hit@1. What holds in both settings: adding the referencing paragraphs to the caption helps (with prefix +2 questions at Hit@1 and +3 at Hit@5; without prefix +1 and +3). The effect of the heading is mixed: with the prefix it lowers Hit@1 (caption 14 → 11 questions, caption + paragraphs 16 → 15); without the prefix it raises Hit@1 for caption + paragraphs (15 → 16) and lowers its Hit@5 (21 → 20). The differences are one to three questions, so we do not conclude that the heading should be kept or dropped; we only note that the SPEC 5.1 composition is not clearly better than caption + paragraphs on this set.

**No-answer questions.** Best cosine score over all figure documents (full, with prefix): 0.580 for Q024 and 0.626 for Q025. The lowest top-1 score among answerable questions is 0.605 (Q018), so a single threshold would still not separate them.

**Caveats.**
- *Different candidate pools.* The chunk baseline ranks 1,080 chunks, the figure index ranks 347 figures. Ranking among fewer candidates makes a top-5 hit easier by itself, so the Hit@5 and MRR gap between the two rows is not a like-for-like gain from the figure documents.
- *Questions written from the figures.* Clara wrote the questions while viewing the caption and the referencing paragraph of each figure. Wording taken from those texts is exactly what a figure document contains, so this set may favour figure documents over chunks, and over the real use, where a learner has not seen the figure. A set written from symptoms, without looking at the figures, is needed before drawing a conclusion.
- *Sample size.* 23 questions, one author: one question moves a metric by about 4.3 points. Every difference above is between one and three questions. With versus without the prefix, the figure-document result goes the other way from 3.1 for Hit@1 (0.696 without, 0.652 with), again one question.
- *Heading rule.* The heading of 10 figures that have referencing paragraphs, and of the figures with no reference, may be empty; the first reference alone decides the heading.

### 3.3 Two handbooks: how results are reported from now on (P7-25)
- **The numbers above are FAA-H-8083-15B only.** Baseline v1 and v2 were measured when 15B was the only handbook, on questions Q001-Q025 written for 15B.
- **Two numbers from now on:** "15B only" (`retrieve(..., handbooks=["FAA-H-8083-15B"])`; comparable with the baseline, and what the older automatic tests and `evaluation/compare_db_files.py` use) and "both handbooks" (default, `handbooks=None`).
- **More than one correct figure.** With two handbooks a question can have several correct figures. Example: "four forces acting on an airplane" -> 15B figure 4-3 (0.812) and 25C figure 3-1, page 3-3 (0.687, rank 5). Which results are acceptable is judged by humans (brief section 8), not by the automatic rule (expected figure at rank 1 / in the top 5), which knows only one figure per question.
- **Cross-handbook case to judge:** Q003 returns 25C figure 17-7 first when both handbooks are searched (15B figure 3-9 is the expected one). Not counted as right or wrong yet; to be judged by a person.

### 3.4 Run on the live search: `evaluation/run_eval.py` (P7-17), 25 questions

Command (repository root, database running): `python evaluation/run_eval.py run 2026-11-06-25q`. Output: [`evaluation/runs/2026-11-06-25q/summary.md`](../evaluation/runs/2026-11-06-25q/summary.md) and `ranked.csv` (the 5 figures returned for every question and scope). Git commit of the code that was measured: 3856093. Tests: `tests/test_run_eval.py`.

**What is measured.** Every question goes through the same code as `GET /search`: `rank()` (the PostgreSQL / pgvector query, top 5, before the threshold) and `retrieve()` (the 0.65 threshold). Two scopes: **own** = only the handbook named in the question (comparable with 3.2), **all** = both loaded handbooks (15B and 25C; what a learner gets). "Auto" counts a hit only when the returned figure is the expected one in the expected handbook (the same figure number in the other handbook does not count).

| Scope | Rule | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | auto (expected figure) | 23 | 0.652 (15/23) | 0.870 (20/23) | 0.743 |
| all | auto (expected figure) | 23 | 0.478 (11/23) | 0.826 (19/23) | 0.634 |
| own / all | human (scored 2, SPEC 5.3) | 0 of 23 fully judged | n/a | n/a | n/a |

**Reading.**
- *own* reproduces exactly the figure-document baseline of 3.2 (0.652 / 0.870 / 0.743), which was computed from the `.npy` files without the database. So the live search (database + `retrieve()`) ranks the figures the same way as the experiment it comes from.
- *all*: for Q001, Q003, Q004 and Q008 a 25C figure is ranked first and the expected 15B figure second; for Q016 the expected figure leaves the top 5 (rank 2 in own). These 25C figures are not counted as hits by the automatic rule, but some may be just as correct (3.3). That is decided by the human judgements, not by this table.
- Still outside the top 5 in both scopes: Q006, Q018, Q020 (the same three as in 3.2).

**Threshold (0.65, FR-002).** No-answer accuracy 2/2 in both scopes (Q024 best score 0.614 over both handbooks, Q025 0.626). One answerable question is refused: Q018 (best score 0.641 in all); its expected figure is not in the top 5 in either scope, so the refusal did not hide a correct figure. The margin is very small: Q017 is answered correctly with 0.653, Q025 (no answer) scores 0.626. **The threshold is still not validated:** it was chosen on these same 25 questions and only 2 of them are no-answer questions. It must be re-checked on the full set with at least 6 no-answer questions (Q026-Q050).

**Human judgements (SPEC 5.3).** `evaluation/judgements.csv` lists every (question, handbook, figure) pair returned for an answerable question: 166 pairs, of which 20 are pre-filled with 2 because they are the expected figure (SPEC 5.3 defines 2 as the expected figure) and 146 are still to be judged by a person (2 / 1 / 0). The script never overwrites a score already written. Judgements are keyed by handbook and printed figure number, so they stay valid after the database is reloaded.

**Limits.** 23 answerable questions, one author, all written for 15B; one question moves a metric by 4.3 points. The 25C handbook has no questions of its own yet (they come with Q026-Q050).

### 3.5 Baseline on the full set: 50 questions (P7-19)

Command: `python evaluation/run_eval.py run 2026-11-07-50q`. Output: [`evaluation/runs/2026-11-07-50q/summary.md`](../evaluation/runs/2026-11-07-50q/summary.md). Code measured: commit a620688. Model BAAI/bge-small-en-v1.5, top 5, threshold 0.65, text chunks and figure documents as in 3.2-3.4. Same two scopes as 3.4 (own, all).

| Scope | Rule | Questions | Hit@1 | Hit@5 | MRR@5 |
| --- | --- | --- | --- | --- | --- |
| own | auto (expected figure) | 42 | 0.643 (27/42) | 0.833 (35/42) | 0.720 |
| all | auto (expected figure) | 42 | 0.524 | 0.786 | 0.639 |
| own / all | human (scored 2, SPEC 5.3) | 0 of 42 fully judged | n/a | n/a | n/a |

**By question type (own scope, counted from the per-question table of the summary).**

| Type | Answerable | Hit@1 | Hit@5 |
| --- | --- | --- | --- |
| topic | 30 | 22/30 = 0.733 | 28/30 = 0.933 |
| symptom | 12 | 5/12 = 0.417 | 7/12 = 0.583 |

Symptom questions are clearly the weakest case: this is the first candidate for the deliberate improvement (section 4).

**Comparison with 3.4.** The 25-question numbers (0.652 / 0.870 / 0.743) and these (0.643 / 0.833 / 0.720) are measured on different sets (23 and 42 answerable questions), so this is not a before/after of an improvement. The slightly lower values come from the harder questions added in Q026-Q050 (9 of the 12 symptom questions).

**Threshold (0.65).** No-answer accuracy: 7/8 (own) and 6/8 (all). Best scores of the 8 no-answer questions in the `all` scope: 0.585 to 0.673 (Q047 = 0.673 and Q046 = 0.651 are above 0.65 and were not refused). Answerable questions refused: 3/42 in own (Q018, Q026, Q031) and 2/42 in all (Q018, Q026); for none of them was the expected figure ranked first. The scores of wrong and right answers overlap: Q047 (no answer) scores 0.673, Q017 (correct) 0.653, so no single threshold separates them perfectly. **The threshold stays provisional (0.65, low-confidence 0.70):** it was observed on this same set and must be fixed only after the human judgements.

**Limits.** No human judgement yet (`evaluation/judgements.csv`: 259 pairs left to judge); one author per half of the set; Q026-Q050 cover only 25C; the "all" numbers are pessimistic because an equally correct figure from the other handbook is not counted as a hit by the automatic rule (3.3).

### 3.6 Reliability of the answer prompt (P7-26, supervisor request of 3 Nov)

**Question.** Does the LLM that writes the answer (Groq `openai/gpt-oss-120b`, temperature 0) follow the system prompt: answer only from the retrieved passages, cite every sentence, invent no number (BR-004), and refuse when nothing answers the question (FR-002)?

**Method.** `python evaluation/prompt_eval.py <run> --prompt v1|v2`. Each of the 50 questions goes through the same path as `GET /answer` (`retrieve(q, 5)` then `generate_answer`), with 3 answer runs per question (retrieval is deterministic). The script counts the sentences the LLM returned, those kept (cited with a valid passage id, numbers present in the cited passages) and those removed by the numeric guard, and records every fallback with its reason and HTTP status. Prompt-quality measures are computed only on runs where the LLM answered (mode `llm`); service failures are reported apart. A seeded sample of 20 kept sentences is written to `citation_check.csv` and judged by a person: `y` when everything the sentence states is in the cited passage, `n` otherwise.

**Runs.**
- `2026-11-09-prompt-v1`: **not interpretable.** 67 of 126 LLM calls ended as `http_error` (the HTTP status was not recorded yet). The script was changed to record the status, retry on 429/5xx and compute the measures on `llm` rows only. Kept as evidence.
- `2026-11-09-prompt-v2`: stopped by the daily free-tier quota (66 `http_error`, 17 with status 429). Not used.
- `2026-11-09-prompt-v1b` and `2026-11-10-prompt-v2`: no HTTP error. These two are compared below.

| Measure (126 answer runs sent to the LLM, 24 refused by retrieval) | v1 (`2026-11-09-prompt-v1b`) | v2 (`2026-11-10-prompt-v2`) |
| --- | --- | --- |
| Runs answered by the LLM (mode `llm`) | 92 | 103 |
| Runs where the LLM returned no sentence (`no_valid_sentences`) | 34 | 23 |
| Sentences kept / returned | 151/154 = 98.1 % | 201/202 = 99.5 % |
| Removed by the numeric guard | 3 | 1 |
| Removed for a missing or unknown citation | 0 | 0 |
| Stability: same cited ids in all 3 runs | 24/31 = 77.4 % | 24/35 = 68.6 % |
| No-answer questions refused by retrieval (runs) | 18/24 | 18/24 |

**What changed in v2 and why.** In v1 the LLM returned no sentence for 10 answerable questions (Q005, Q006, Q011, Q019, Q020, Q031, Q036, Q037, Q043 on all 3 runs, Q042 on 1). For several of them the expected figure was ranked first: the stored text only points to the figure ("A precision approach path indicator ... [Figure 14-30]"), and the actual answer (light colours, light-gun signals, oil flow) is in the drawing. v2 (`backend/prompts/answer_system_v2.txt`) adds two rules: (1) when a passage is about the topic but its text does not give the full answer, state what the text says and point to the figure by its number; (2) do not add causes, consequences or general rules the passage does not state. Result: Q006, Q019, Q037, Q043 are now answered on every run and Q005 on 2 of 3 (for example Q043: "In a wet-sump system the oil is located in a sump that is an integral part of the engine. [888] Figure 7-17 shows this wet-sump oil system. [888]"). Q011, Q020, Q031 and Q036 are still refused.

**Citation support (human judgement, v2, `evaluation/runs/2026-11-10-prompt-v2/citation_check.csv`).** 15/20 sentences are fully supported by the cited passage (75 %). The 5 others: one inference not in the passage (row 1, Q030), one sentence mixing two instruments (row 12, Q009), one reversed statement (row 18, Q009), and two sentences completed beyond a stored passage that is cut mid-sentence (rows 19 and 20, Q039 and Q027).

**Reading.**
- The automatic checks work as designed: no uncited sentence and no unknown id reached the reader, and the numeric guard removed the sentences with an unsupported number.
- They do not catch a wrong statement that cites a real passage and contains no number: 5 of 20 sampled sentences. This is the main limit of the answer layer, and the reason the figure, caption, handbook and page are always shown next to the text (BR-002).
- Stability is lower in v2 on more questions (35 vs 31). With one run per prompt, differences of a few points are within noise; v2 is kept because it answers more figure-type questions without lowering the share of kept sentences.

**Problems found, to fix outside the prompt.**
- **Truncated passages.** Some stored referencing paragraphs stop mid-sentence (FAA-H-8083-25C figures 7-21 and 16-19 here, and db id 777 noted earlier). The LLM then completes them. Ingestion backlog: keep whole sentences.
- **No-answer fallback (FR-002, UC-02 A1).** For Q046 and Q047 (no answer in the corpus) the LLM correctly returned no sentence on all 6 runs, but `generate_answer` then falls back to the extractive answer and shows the retrieved passages. FR-002 asks for a clear "no answer found" instead of a weak match. To change in `backend/answer.py`, measured separately so that this comparison only changes the prompt.

### 3.7 Joint retrieval over text and images (P7-30)

**Requirement.** Brief section 4: "joint retrieval over text and images"; SRS UC-02 step 3: "the system searches the stored text and figures together". Neither document says how. The modes below are the team's choices, measured on the same 50 questions as 3.5 (code: branch `feature/P7-30-joint-retrieval`, `backend/retrieval.py`, `RETRIEVAL_MODE`).

| Mode | What is compared with the question |
| --- | --- |
| `text` (3.5, unchanged) | the figure document: section heading + caption + citing paragraphs (bge-small, 384 dims) |
| `image` | the figure **picture**: CLIP `clip-ViT-B-32` (sentence-transformers, 512 dims) on the PNG, `ingestion/embed_images.py`, table `figure_image_embeddings` (migration 006) |
| `joint` | `text` and `image` rankings fused with Reciprocal Rank Fusion, score = sum of 1/(60 + rank) (Cormack, Clarke and Buettcher, SIGIR 2009; k = 60 not tuned), 50 candidates per list |
| `passages` | the 100 handbook chunks nearest to the question; a chunk that mentions "Figure 3-3" gives its score to figure 3-3 (`figure_mentions`; 388/388 mentions in 15B and 542/543 in 25C match a stored figure) |
| `hybrid` | `text` and `passages` rankings fused with RRF |

In every mode the "no answer" decision and the confidence use the text similarity of the best `text` match (threshold 0.65, low confidence 0.70), so no-answer handling is the same in all modes. Image and chunk searches read only `searchable_*` views (BR-001); tests check this.

**Commands.** `python ingestion/embed_images.py` (849 of 849 figures embedded, no missing image), then `python evaluation/run_eval.py run 2026-11-11-<mode> <mode>` for the five modes. Outputs: `evaluation/runs/2026-11-11-{text,image,joint,passages,hybrid}/`. The `text` run reproduces 3.5 exactly (0.643 / 0.833 / 0.720): the new code did not change the existing search.

**Results (automatic rule: the expected figure; 42 answerable questions).**

| Mode | own Hit@1 | own Hit@5 | own MRR@5 | all Hit@1 | all Hit@5 | all MRR@5 |
| --- | --- | --- | --- | --- | --- | --- |
| text | **0.643** | 0.833 | **0.720** | **0.524** | **0.786** | **0.639** |
| image (CLIP) | 0.071 | 0.190 | 0.115 | 0.048 | 0.143 | 0.080 |
| joint (text + CLIP) | 0.167 | 0.381 | 0.260 | 0.167 | 0.381 | 0.238 |
| passages | 0.571 | **0.857** | 0.683 | 0.405 | 0.786 | 0.569 |
| hybrid (text + passages) | 0.595 | 0.833 | 0.698 | 0.476 | 0.762 | 0.611 |

By question type (own scope, Hit@1 / Hit@5 / MRR@5):

| Type | text | passages | hybrid |
| --- | --- | --- | --- |
| topic (30) | 0.733 / 0.933 / 0.819 | 0.633 / 0.967 / 0.772 | 0.667 / 0.933 / 0.786 |
| symptom (12) | 0.417 / 0.583 / 0.472 | 0.417 / 0.583 / 0.461 | 0.417 / 0.583 / 0.479 |

No-answer accuracy is 7/8 (own) and 6/8 (all) in every mode, as expected from the shared threshold.

**Reading.**
- **The picture alone does not find the figure.** CLIP puts the expected figure in the top 5 for 8 of 42 questions. It was trained on photographs with everyday captions; our figures are technical line drawings full of labels. Example Q001 (airspace classes): text ranks figure 1-1 first; CLIP returns 4-10, 4-11, 4-5, 5-15, 4-4. Fusing such a list with the text list (`joint`) pulls good text results down: Hit@1 falls from 0.643 to 0.167.
- **Passages help slightly at rank 5, not at rank 1.** `passages` finds one more expected figure in the top 5 (36 vs 35 of 42) but ranks fewer first. `hybrid` is better on 4 questions and worse on 5 compared with `text`. With 42 questions, these differences are within noise.
- **No mode helps the symptom questions** (same 5/12 at rank 1 and 7/12 in the top 5). Their problem is analysed in section 4.
- These numbers use the automatic rule only. A mode can return another figure that a person would judge equally correct (for example Q002: 3-4 instead of 3-3). The human judgements (SPEC 5.3) may change the differences above; the runs are kept so they can be re-scored with `run_eval.py score`.

**Decision.** The live search stays in `text` mode (the default of `RETRIEVAL_MODE`); CLIP is not loaded in that mode, so it costs no memory on the server. The other modes stay in the code, switchable and measured, as evidence. **TO CONFIRM WITH SUPERVISOR:** whether retrieving figures through their caption, citing paragraphs and handbook passages, with the picture-based (CLIP) experiment reported as a measured negative result, satisfies "joint retrieval over text and images".

### 3.8 LLM refusal on a weak match becomes "no answer" (FR-002 fix)

**Problem (found in 3.6 and in the app on 12 Nov).** When the LLM returned no sentence (prompt v2, rule 8: no passage is about the question), `generate_answer` treated it like a failure and fell back to the extractive answer, so the retrieved passages and figures were still shown. Example in the app: "what is the salary of an airline pilot" showed Figure 1-22 of 25C with the low-confidence notice. FR-002 and UC-02 A1 ask for a clear "no answer found" and no weak match.

**Rule (our choice, from our own measures).** In `backend/answer.py`: if the LLM returns no sentence **and** retrieval marked the match as low confidence (best score under 0.70), the answer is `no_answer` (`fallback_reason` = `llm_refused_low_confidence`) and `GET /answer` returns no figure; the query log records it as `no_answer` (FR-007). A refusal on a high-confidence match keeps the extractive answer and the figure. A service failure (timeout, HTTP error, missing key, bad JSON) is unchanged.

**Why not "refusal = no answer" everywhere.** In the 10 Nov v2 run the LLM also refused answerable questions whose figure was right: Q036 (expected figure ranked 1, score 0.80), Q011 (expected figure in the top 5, 0.75), and Q005 on one run (ranked 1, 0.71). Every refused question scoring under 0.70 was either a no-answer question (Q046, Q047) or had no expected figure in the top 5 (Q031, Q032), checked against `evaluation/runs/2026-11-11-text/ranked.csv`.

**Measure.** `python evaluation/prompt_eval.py 2026-11-12-refusal --prompt v2 --runs 1` (same 50 questions, same path as `GET /answer`, git commit acb8c4d + this change).

| Measure | Before (`2026-11-10-prompt-v2`, 3 runs) | After (`2026-11-12-refusal`, 1 run) |
| --- | --- | --- |
| No-answer questions answered "no answer" | 18/24 runs = 6/8 questions (Q046, Q047 showed passages) | **8/8** |
| Answerable questions turned into "no answer" by the new rule | - | 2: Q031, Q032 (neither had the expected figure in the top 5) |
| Answerable questions refused by the LLM on a confident match, figure kept (extractive) | - | 4: Q006, Q011, Q020, Q036 |
| Sentences kept / returned (mode `llm`) | 201/202 = 99.5 % | 62/63 = 98.4 % |
| http_error rows | 0 | 0 (17 calls retried after HTTP 429, all recovered) |

**Reading.** The two no-answer questions that used to show a weak match are now refused, and the two answerable questions that became "no answer" were showing a wrong figure anyway, so no correct figure was lost on this set. Figure-retrieval metrics (3.5) do not change: they are computed by `run_eval.py` on `retrieve()`, before the answer layer.

**Limits.** One run (the LLM is not fully stable, 3.6); 0.70 is the provisional low-confidence threshold chosen on this same set, so the rule is not validated on unseen questions; the human judgements (FR-005) are not done yet. The fix is visible in the app only when the search page calls `GET /answer` (it calls `GET /search` today; frontend task).

### 3.9 The cumulative chat (P7-55; supervisor meeting of 13 Nov)

**What is measured.** The chat (`POST /chat`, `backend/chat.py`, SPEC FR-009) with the live settings: Gemini embeddings (thresholds 0.64 / 0.66), Groq `gpt-oss-120b`, prompts `chat_rewrite_v1` and `chat_answer_v3`, all handbooks. Script `evaluation/chat_eval.py`, run `evaluation/runs/2026-11-14-chat` (part A at 12:09 UTC, part B at 12:41 UTC, commit `c086f4a`), 20 s between questions to stay under Groq's free-tier limits.

**A. The 50 questions as the first message of a chat.**

| Measure | Result |
| --- | --- |
| Answer written by the LLM (cited, numeric guard passed) | 39 / 42 answerable |
| Extractive answer (every LLM sentence removed by the citation or number check) | 3 / 42: Q011, Q036, Q037 (`no_valid_sentences`) |
| No-answer questions answered "no answer" | **8 / 8** (Q025 by the P7-50 rule: LLM refusal on a low-confidence match) |
| Answerable questions answered "no answer" | **0 / 42** |
| First figure = expected, retrieval order (score) | Hit@1 31/42, Hit@5 38/42 |
| First figure = expected, order shown by the chat (cited figures first) | Hit@1 32/42, Hit@5 38/42 |

Showing the figures cited by the answer first gains one question at rank 1 and loses none.

**B. Follow-up questions.** `evaluation/chat_followups.csv`: 10 pairs "first question -> follow-up with a pronoun" (for example "What is a VOR?" -> "How are its radials represented?"). The expected figure of each follow-up is the expected figure of an existing question of the 50 (column `source_question`). Each follow-up is searched with the history (the real chat: first answer in the history, follow-up rewritten by the LLM) and without it (as a search box).

| Follow-up searched | Hit@1 | Hit@5 |
| --- | --- | --- |
| with history (chat, rewritten) | 7 / 10 | **10 / 10** |
| without history (search box) | 6 / 10 | 7 / 10 |

- The follow-ups whose only topic word is the pronoun fail without history and succeed with it: F07 ("What do its lights show...", PAPI), F08 ("How do I use it...", segmented circle), F09 ("How do I read it?", V-g diagram): not in the top 5 -> rank 1.
- 9 of the 10 rewrites replaced the pronoun with the right subject. **F04 is wrong:** "if it gets blocked" was rewritten as "if the airspeed indicator gets blocked" instead of the pitot-static system (the expected figure is still at rank 4, same as without history).
- The rewrite can also move the expected figure down when the follow-up already named its subject: F01 (rate gyro: rank 1 -> 3) and F10 (density altitude: 1 -> 2).
- No rewrite failed (no fallback).

**Limits.**
- The 10 pairs were drafted with AI help (Claude) and marked "to review" in the file; they are a small extra set for the chat, not part of the 50-question evaluation set.
- One run of a language model at temperature 0; the answers can still vary between runs.
- The quality of the answer text itself (is every sentence supported by its cited passage?) was measured on the earlier prompt (3.6: 15/20 sentences fully supported) but not yet on prompt v3: to do with a human check of a sample of answers.
- The free tiers limit how fast this can be run (Groq: 8,000 tokens a minute, 200,000 a day; Gemini: about 1,000 embedding requests a day).

## 4. Deliberate improvement: before and after (Week 10)

### 4.1 Experiment 1: query reformulation (P7-33)

**Why this experiment.** Section 3.5 shows that symptom questions are the weak case (own scope: Hit@1 5/12, Hit@5 7/12). In the text run, every symptom question that fails describes an effect without naming it (Q020 pitot blockage, Q031 microburst, Q032 ground effect, Q033 adverse yaw, Q034 P-factor), while the ones that succeed share words with the handbook. None of the retrieval modes of 3.7 helped them.

**Hypothesis (written before the run).** Rewriting the question in handbook vocabulary with the LLM, then fusing the ranking of the rewritten question with the ranking of the original one, raises Hit@5 on the symptom questions without lowering the topic questions or the no-answer accuracy.

**Method.**
- `backend/reformulate.py`: one Groq call per question (`openai/gpt-oss-120b`, temperature 0, JSON output). Two prompts, both committed before the run (commit `5d006e6`) and not changed after it: `reformulate_v1.txt` (strict: handbook words only, no cause, no new fact) and `reformulate_v2.txt` (the same, plus up to 3 handbook topics given as search terms, never as the cause). A test checks that the prompts contain none of the 50 questions and none of the expected answers of the symptom questions.
- Mode `reformulated` in `backend/retrieval.py`: the original question and the rewritten one are each ranked (50 candidates), and the two lists are fused with RRF (k = 60, as in 3.7). If the rewrite fails, the original question alone is used.
- The "no answer" decision and the confidence still use the score of the **original** question, so a rewrite can reorder figures but cannot turn a question without an answer into an answered one. A test checks this.
- Commands: `python evaluation/run_eval.py run 2026-11-11-reform-v1 reformulated v1` and `... reform-v2 reformulated v2`, same 50 questions. The rewrites are in `evaluation/runs/2026-11-11-reform-v*/reformulations.csv`.

**Results (automatic rule, own scope; baseline = `2026-11-11-text`, identical to 3.5).**

| Questions | Baseline (text) | Rewrite v1 (strict) | Rewrite v2 (topics) |
| --- | --- | --- | --- |
| all 42 answerable: Hit@1 / Hit@5 / MRR@5 | 0.643 / 0.833 / 0.720 | 0.619 / 0.833 / 0.695 | 0.619 / 0.810 / 0.688 |
| topic (30) | 0.733 / 0.933 / 0.819 | 0.700 / 0.900 / 0.775 | 0.733 / 0.900 / 0.806 |
| symptom (12) | 0.417 / 0.583 / 0.472 | 0.417 / 0.667 / 0.496 | 0.333 / 0.583 / 0.394 |
| no-answer accuracy | 7/8 | 7/8 | 7/8 |

All scope (both handbooks), all 42 answerable: baseline 0.524 / 0.786 / 0.639; v1 0.476 / 0.762 / 0.591; v2 0.524 / 0.714 / 0.604.

Questions that moved (own rank of the expected figure, baseline -> rewrite):
- v1: better Q011 (4->3), Q026 (3->2), Q033 (not in top 5 -> 4); worse Q012 (2 -> not in top 5), Q015 (3->4), Q016 (2->3), Q030 (3->5), Q039 (1->3).
- v2: better Q011 (4->2), Q015 (3->2), Q016 (2->1), Q033 (- ->5), Q040 (2->1); worse Q012 (2->-), Q017 (1->3), Q026 (3->5), Q028 (1->3), Q030 (3->-), Q039 (1->3).

**Cost.** 50 LLM calls per run, no failure and no retry (6 s pause between calls). Median time of a rewrite: 814 ms (v1), 1199 ms (v2). In the live search this would add about one second to every answered question (the LLM is not called when the original question is refused).

**Reading.**
- **The hypothesis is not confirmed.** v1 gains one symptom question in the top 5 (Q033) and loses topic questions; v2 is worse on symptoms. With 12 symptom questions, one question is 8 points: these differences are within noise.
- **Naming the phenomenon was not enough.** v2 named the right topic for Q031 ("microburst"), Q032 ("ground effect") and Q033 ("Adverse Yaw"), and still the expected figure was not ranked first. Two likely reasons, not yet verified: (1) RRF gives the same weight to the original list, which does not contain the expected figure, so a figure found only by the rewrite falls behind figures found by both; (2) the stored text of the expected figure is weak: the citing paragraphs of 12-17 and 5-17 start in the middle of a sentence (the truncation found in 3.6), so the sentence that names the phenomenon is not in the searched text.
- **The strict prompt was not always followed.** The v1 rewrite of Q033 says "adverse yaw", which is the answer: the rule "do not name a cause" was broken. A person must still check every rewrite (`check` column of `reformulations.csv`: faithful / cause_added / intent_changed) before these runs are used further.
- No-answer accuracy is unchanged, as designed.

**Decision.** Query reformulation is **not** adopted: the live search stays in `text` mode and calls no LLM before retrieval. The result is reported as measured (SRS UC-06 A2). The next candidate for the deliberate improvement targets the cause found here, the stored text of the figures (whole citing sentences at ingestion), measured on the same 50 questions. **TO CONFIRM WITH SUPERVISOR:** whether a measured negative result can count as the deliberate improvement, or whether a second, positive attempt is expected; and whether an LLM may be used before retrieval at all.


### 4.2 Experiment 2: embedding model, bge-small vs Gemini (P7-57, supervisor request of 13 Nov)

**Why this experiment.** At the 13 Nov meeting the supervisor asked for a small hosted embedding model, the same at ingestion and at search time, and said that both OpenAI and Gemini were acceptable: "check which one suits your data best". Section 4.1 also showed that the symptom questions fail because their words do not match the stored text; a stronger embedding model is a direct way to close that vocabulary gap.

**Hypothesis.** `gemini-embedding-001` ranks the expected figure higher than `BAAI/bge-small-en-v1.5` on the same 50 questions, especially on symptom questions, without hurting the no-answer path once its thresholds are set. (Recorded here after the meeting decision but before any threshold was chosen; it was not committed before the run.)

**Method.**
- Same figure documents as bge (caption + first citing paragraph, `figures.search_text`), embedded with `gemini-embedding-001`, 768 dimensions, task type RETRIEVAL_DOCUMENT; questions embedded with task type RETRIEVAL_QUERY (`backend/embedding.py`, `ingestion/embed_text.py`). Vectors stored next to the bge ones (migration 010), so only the model changes. 849 of 849 figures embedded.
- Same 50 questions, same `text` mode, same automatic rule (expected figure). Run `evaluation/runs/2026-11-13-gemini`, with both thresholds at 0, so every question returns its top 5 and the scores can be read before choosing thresholds.
- Baseline = `2026-11-11-text` (bge-small, section 4.1).

**Results (automatic rule; Hit@1 / Hit@5 / MRR@5).**

| Questions | Scope | bge-small (`2026-11-11-text`) | Gemini (`2026-11-13-gemini`) |
| --- | --- | --- | --- |
| all 42 answerable | own | 0.643 / 0.833 / 0.720 | **0.881 / 0.929 / 0.905** |
| topic (30) | own | 0.733 / 0.933 / 0.819 | 0.933 / 0.967 / 0.950 |
| symptom (12) | own | 0.417 / 0.583 / 0.472 | 0.750 / 0.833 / 0.792 |
| all 42 answerable | all | 0.524 / 0.786 / 0.639 | **0.738 / 0.905 / 0.808** |
| topic (30) | all | 0.600 / 0.900 / 0.736 | 0.833 / 0.933 / 0.878 |
| symptom (12) | all | 0.333 / 0.500 / 0.396 | 0.500 / 0.833 / 0.632 |

Still not in the top 5 with Gemini (both scopes): Q006 (15B 4-7), Q030 (25C 17-5), Q032 (25C 5-17). With both handbooks, a figure of the other handbook is often first (Q001, Q004, Q020, Q022, Q033, Q034): the two handbooks cover the same topics.

**Thresholds (PROVISIONAL).** Gemini scores are on another scale than bge and are compressed (top-1 scores about 0.56-0.82), so the bge thresholds (0.65 / 0.70) cannot be reused. All scope top-1 scores: no-answer questions 0.564-0.652 (highest Q025 0.652, then Q047 0.639); lowest correct answerable 0.645 (Q005, Q027). Chosen: **no answer below 0.64, low confidence below 0.66** (`MODEL_THRESHOLDS` in `backend/retrieval.py`). Expected effect on this set: 7/8 no-answer questions refused, no answerable question refused; Q025, Q005, Q027 and Q032 shown with the low-confidence notice, and in the chat the P7-50 rule turns an LLM refusal on a low-confidence match (expected for Q025) into "no answer". Confirmed by the run with these thresholds (`2026-11-13-gemini-t`, 13 Nov): no-answer accuracy 7/8 in both scopes (Q025 answered, with the low-confidence notice), 0/42 answerable questions refused; Hit@1 / Hit@5 / MRR unchanged (thresholds only decide whether to answer).

**Limits.**
- The thresholds were chosen on the same 50 questions they are tested on (same limit as bge, section 3.5); the margin is very small (0.645 vs 0.652).
- Automatic rule only; the human judgements (`judgements.csv`, 397 pairs still to judge) are not done yet.
- Gemini is a hosted API: each question costs one request (free tier) and adds network time; if the API fails, the question fails (no local fallback yet).
- One run (embeddings are deterministic, so a re-run should give the same ranking).

**Decision.** `gemini-embedding-001` replaces bge-small for ingestion and search (`EMBEDDING_MODEL=gemini-embedding-001`); the answer is still written by Groq `gpt-oss-120b`. bge-small vectors are kept in the database for the comparison. OpenAI `text-embedding-3-small` was not measured (paid account needed); it can be compared the same way with `ingestion/embed_text.py text-embedding-3-small`.
