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

### 1.3 Errors and limitations observed

| Error type | Examples | Cause | Status |
| --- | --- | --- | --- |
| Crop includes surrounding body text | 9-6, 10-2 (sample); 9-19, 9-20, 9-21, 11-13, 11-2 (found while browsing, outside the sample); 1-15 | Raster images placed partly off the page or larger than their visible area (e.g. PDF page 263: an image spans x = 189 to 693 on a 594 pt wide page). The PDF crops them, but the extractor uses the full image rectangle. The v3 clipping fix covers vector drawings only, not images. The labels inside these crops are short, so the `needs_review` check (paragraph > 250 characters) did not flag them. | **Fixed in v4 (P7-4):** boxes are shrunk to their visible ink. 9-19, 9-20, 9-21, 11-13, 11-2, 1-15, 9-6 and 10-2 checked by eye after the fix: no body text left. |
| Caption included in the image | 5-39, 9-21 | The caption overlaps the bottom of the artwork region, so the crop includes it | **Fixed in v4:** 5-39 checked by eye, caption no longer in the image. |
| Caption found but no figure region | v3: 13 figures; v4: 3 (6-6, 7-1, 7-49); v5: 0 | Mostly one oversized image covering two figures, so one caption took the whole box and the other found nothing. v4 cuts such a box at the caption. | 3 left for the QA queue |
| Crop still contains body text | v4: 2-4, 6-37, 7-47 | Figure and text are interleaved in ways a rectangle cannot separate | v5: 3 left (5-7, 6-33, 10-10), flagged `needs_review` for the QA queue |
| Found by Clara after v4 (28 Oct): 6-6 and 7-49 missing; caption inside 1-18, 1-19, 5-37, 10-1; 5-38 inside 5-37, 5-51 inside 5-52; text in 6-5, 6-7, 6-37, 7-47, 1-17; 6-35, 8-5, 6-20 cut off | 15 figures | Side-by-side figures joined across the ~11 pt column gap; an oversized image keeping other figures' ink; the 6 pt image margin reaching into the caption; labels and separate side pieces left outside the box | **Fixed in v5 (P7-5)**, each case checked by eye on its page |
| Excel converted figure numbers to dates while judging ("1-20" became "20-Jan") | all 20 rows | Excel's automatic date detection when opening a CSV | Fixed: `sample_check.py score` restores both columns from `figures.jsonl`. The committed evidence file has the restored values; the y/n judgements are unchanged. |

## 2. Evaluation set (Week 3)
*(50+ questions, each with the expected figure identified by handbook and printed page)*

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

## 4. Deliberate improvement: before and after (Week 10)
