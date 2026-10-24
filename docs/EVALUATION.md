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
(the counts below come from `data/extracted/FAA-H-8083-15B/report.json`)

| Count | Value |
| --- | --- |
| PDF pages | 371 |
| Captions found ("Figure X-Y.") | 347 |
| Figures bound to a caption | 334 (96.3 %) |
| Captions with no figure region (sent to QA) | 13 |
| Unbound graphic regions (sent to QA) | 35 |
| Bound figures flagged `needs_review` (crop contains a body paragraph) | 8 |
| Figures with at least one referencing paragraph | 341 |
| Figures missing a printed page number | 0 |

The same counts were obtained on two machines (Windows laptop and a Linux environment) from the same PDF (same SHA-256).

Captions per chapter: 1: 24, 2: 16, 3: 9, 4: 23, 5: 60, 6: 39, 7: 75, 8: 20, 9: 43, 10: 20, 11: 18.

**Extractor iterations on this handbook** (same PDF, same caption detector):

| Version | Bound | Caption only | Unbound regions | Change |
| --- | --- | --- | --- | --- |
| v1 | 277 | 70 | 72 | first run |
| v2 | 298 | 49 | 61 | no merge across a caption; sideways captions bind to the left |
| v3 | 334 | 13 | 35 | vector paths cut to their clipping area; caption overlapping the bottom of its artwork accepted |

Caption-only figures (v3): 2-4, 5-49, 5-56, 6-6, 6-7, 6-18, 6-28, 6-35, 7-1, 7-2, 7-48, 7-49, 11-14.
Flagged for review (v3): 1-17, 5-7, 6-33, 7-3, 7-39, 7-47, 7-68, 10-10. Known bad crop not flagged: 1-15 (includes surrounding text).

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

Incomplete images in the sample: 5-39 and 9-21 (caption included in the image), 9-6 and 10-2 (part of the surrounding text included). No caption was bound to the wrong image.

With 20 pairs, 20/20 is consistent with a true caption-binding accuracy anywhere from about 84 % to 100 % (95 % Wilson interval); a larger sample would narrow this.

### 1.3 Errors and limitations observed

| Error type | Examples | Cause | Status |
| --- | --- | --- | --- |
| Crop includes surrounding body text | 9-6, 10-2 (sample); 9-19, 9-20, 9-21, 11-13, 11-2 (found while browsing, outside the sample); 1-15 | Raster images placed partly off the page or larger than their visible area (e.g. PDF page 263: an image spans x = 189 to 693 on a 594 pt wide page). The PDF crops them, but the extractor uses the full image rectangle. The v3 clipping fix covers vector drawings only, not images. The labels inside these crops are short, so the `needs_review` check (paragraph > 250 characters) did not flag them. | Open: next extractor fix (clip images to their visible area) |
| Caption included in the image | 5-39, 9-21 | The caption overlaps the bottom of the artwork region, so the crop includes it | Minor: the figure is still correct; to fix with the item above |
| Caption found but no figure region | 13 figures, listed in 1.1 | Not yet analysed | Open (QA queue) |
| Excel converted figure numbers to dates while judging ("1-20" became "20-Jan") | all 20 rows | Excel's automatic date detection when opening a CSV | Fixed: `sample_check.py score` restores both columns from `figures.jsonl`. The committed evidence file has the restored values; the y/n judgements are unchanged. |

## 2. Evaluation set (Week 3)
*(50+ questions, each with the expected figure identified by handbook and printed page)*

## 3. Baseline retrieval results (Week 3)

## 4. Deliberate improvement: before and after (Week 10)
