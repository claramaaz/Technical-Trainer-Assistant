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

**Comparison with the figure list in the handbook** (the brief asks for this): *(how many figures the handbook itself numbers, per chapter, compared with the captions found; explain any gap)*

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

## 4. Deliberate improvement: before and after (Week 10)
