# Software Requirements Specification — Technical Training Assistant (P7)

## 1. Document Information

| Field | Value |
| --- | --- |
| Project Name | Technical Training Assistant (Project P7) |
| Document Title | Software Requirements Specification |
| Course | Software Engineering — ESIB, Université Saint-Joseph |
| Team Members | Mia Badran – Clara Maaz |
| Instructor / Supervisor | Mr. Georges Salloum |
| Version | 1.1 |
| Date / Status | 19/10/2026 — Baseline, tagged `spec-v1` before the first implementation commit |

### 1.1 Change log

| Version | Date | Change |
| --- | --- | --- |
| 0.1 | 04/10/2026 | First draft (Word). |
| 1.0 | 19/10/2026 | Converted to Markdown. Added section 5 (chunking strategy, page numbering, evaluation metrics), FR-009 (answers with cited sources), low-confidence handling in FR-002, decisions for UC-04 A2 and UC-07, stack decisions (2.5), corrected cross-references. |
| 1.1 | 28/10/2026 | 5.1: chunk size cap set to 200 words from the measurement of FAA-H-8083-15B; embedding model must accept ≥ 512 tokens; content covered by chunking listed. |

Any later divergence from this document is recorded in this change log with its reason.

## 2. Introduction

### 2.1 Purpose

Technical manuals explain equipment mainly through diagrams, and a system that only returns text hides the answer a learner actually needs. This document defines the requirements for a web-based system that answers a technical question with the matching explanation text and the correct diagram, sourced from FAA aviation handbooks, so a trainee can find and verify the right figure quickly, including on a phone.

### 2.2 Scope

The system lets a learner ask a question and receive explanatory text plus the matching diagram, with the handbook name and page number. An admin area lets whoever loads the manuals check ingestion, fix incorrectly extracted figures, and monitor usage. The corpus is FAA handbooks and manuals (public domain PDFs). Out of scope: native mobile apps, other data sources beyond the optional NASA NTRS / PubMed Central stretch corpora, and any safety-critical operational guidance.

### 2.3 Stakeholders and Users

| Stakeholder / User | Type | Role / Interest in the System |
| --- | --- | --- |
| Learner / Trainee | User | Asks a technical question and views the returned text and diagram, often on a phone. |
| Admin (corpus operator) | User | Loads handbooks, reviews and corrects extracted figures, monitors usage and failures. |
| Supervisor / Assessor | Stakeholder | Reviews the deployed system and this document against the project brief. |

#### 2.3.1 Main Actors

**A. Primary actors (human)**

| Actor | Goal | What the actor does in the system | Use cases |
| --- | --- | --- | --- |
| Unauthenticated visitor | Reach the system and sign in. | Can only see the login page. Cannot search, see figures or open any admin page. | UC-05 |
| Learner / Trainee (role: Learner) | Find the right explanation and diagram for a technical topic or symptom, and trust it. | Logs in and logs out. Types a topic or symptom and submits it, usually from a phone on a slow connection. Reads the returned procedure text and views the figure, its caption, handbook name and page number. Opens the source to verify the figure against the original page. Flags a figure that does not match the question. Reads the "no answer found" message when nothing relevant exists. | UC-02, UC-03, UC-05, UC-07 |
| Admin / Corpus operator (role: Admin) | Keep the corpus complete and correct, and keep the system running. | Logs in and sees the admin screens (inaccessible to Learners). Starts the ingestion of a handbook and checks its report (figures extracted, captions bound, licence recorded). Reviews the QA queue of flagged or low-confidence figures and corrects the caption, page or reference link, or removes the figure. Checks the coverage map by handbook and chapter. Monitors query volume, latency, failure rate and unanswered questions. Triggers re-indexing after corrections or changes. | UC-01, UC-04, UC-05, UC-08, UC-09, UC-10 |
| Development team (evaluators) | Demonstrate with measurements that the returned figure is the right one. | Writes the 50+ question evaluation set (expected figure by handbook and page). Runs the set and records human relevance judgements. Measures caption-binding accuracy and page-citation (provenance) correctness, before and after the deliberate improvement. | UC-06 |
| Supervisor / Assessor (stakeholder) | Check the deployed system and this document against the project brief. | Opens the public URL and exercises the system as a Learner or Admin. Has no dedicated role. | - |

**B. Secondary actors (external systems)**

| Actor | Service provided to the system | Used in |
| --- | --- | --- |
| FAA handbooks website | Index page and stable PDF URLs of the handbooks (primary corpus, public domain). | UC-01 |
| NASA NTRS API; PubMed Central Open Access (S3) | Optional stretch corpora. Only used if approved; licence is read per article for PMC. | UC-01 (optional) |
| Embedding / language model service | Produces embeddings used for retrieval and, where a generated answer is shown, drafts it from retrieved passages only (BR-004). | UC-01, UC-02, UC-10 |

### 2.4 Definitions, Acronyms and Abbreviations

| Term / Acronym | Definition |
| --- | --- |
| Figure | An embedded diagram or image extracted from a handbook PDF. |
| Caption binding | Linking an extracted figure to its caption text. |
| Referencing paragraph | A paragraph of handbook text that cites a figure by its number (e.g. "Figure 4-12"). |
| Chunk | A unit of handbook text stored and searched as one item (see 5.1). |
| Figure document | The searchable text built for one figure: its caption, its referencing paragraphs and its section heading (see 5.1). |
| Provenance | The handbook name and page number that let a reader verify a source. |
| Printed page number | The page number printed on the handbook page (e.g. "4-12"), as opposed to the position of the page in the PDF file (see 5.2). |
| Actor | A user or external system that interacts with the system (see 2.3.1). |
| Use case | A described sequence of interactions between an actor and the system that achieves a goal (see 6.1). |
| QA queue | The admin list of figures flagged as wrong by a learner or by low search confidence. |

### 2.5 Assumptions, Dependencies and Technology Decisions

The FAA handbook index and PDF URLs remain stable. Figure extraction quality varies by document and is validated on one handbook before scaling to others. As directed by the supervisor, the system is built in Python, exposes an API consumed by a web interface, and project tasks are tracked in Jira.

| Concern | Decision | Status |
| --- | --- | --- |
| Backend language | Python | Confirmed (supervisor) |
| Database and vector store | PostgreSQL with pgvector | Confirmed (supervisor) |
| API framework | FastAPI | Confirmed |
| Frontend | React (responsive web, no native app) | Confirmed |
| PDF extraction | PyMuPDF | Confirmed |
| Figure images | Stored as files in object storage; the database stores their path | Confirmed |
| Embedding model | Chosen in Week 3 on the baseline evaluation; recorded here when chosen. Must accept at least 512 input tokens (5.1) | Open |
| Language model for answers | Chosen in Week 4; recorded here when chosen | Open |
| Hosting | Chosen before Week 6; recorded here when chosen | Open |
| Task tracking | Jira | Confirmed (supervisor) |

## 3. Functional Requirements

### FR-001 - Load Handbook Data

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-001 |
| Title | Load Handbook Data |
| User-Level Requirement | The admin shall be able to load FAA handbook PDFs into the system. |
| System-Level Requirement | The system shall extract text and figures from each handbook PDF, bind each figure to its caption, to the page it appears on and to the paragraphs that reference it, chunk the text as described in 5.1, and store the result in the PostgreSQL database (pgvector). The system shall record the source URL, licence and retrieval date for each document. |
| Primary User(s) | Admin |
| Priority | Must |
| Acceptance Criteria | Loading a handbook produces stored text, figures and captions retrievable from the database, with a licence recorded for that document. |

### FR-002 - Search for an Answer

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-002 |
| Title | Search for an Answer |
| User-Level Requirement | The learner shall be able to ask a technical question and receive the matching explanation and diagram. |
| System-Level Requirement | The system shall search the stored text and figures together and return matching passages and figures, each with handbook name and page number. The system shall classify each result as a match, a low-confidence match or no match, using score thresholds set on the evaluation set. A low-confidence match shall be shown with a visible low-confidence notice. If no adequate match is found, the system shall clearly state that no answer was found instead of returning a weak match. |
| Primary User(s) | Learner |
| Priority | Must |
| Acceptance Criteria | Entering a topic returns text and a diagram with their source; a low-confidence result carries a visible notice; a question with no relevant content returns a clear no-match message. |

### FR-003 - Review and Correct Figures

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-003 |
| Title | Review and Correct Figures |
| User-Level Requirement | The admin shall be able to review and fix figures that were extracted or matched incorrectly. |
| System-Level Requirement | The system shall list figures flagged as incorrect, by a user or by low search confidence, and allow the admin to correct the caption/page link or remove the figure. Corrections shall apply to later searches. |
| Primary User(s) | Admin |
| Priority | Must |
| Acceptance Criteria | An admin can find a flagged figure, correct or remove it, and the fix is reflected in a later search. |

### FR-004 - User Accounts and Roles

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-004 |
| Title | User Accounts and Roles |
| User-Level Requirement | Learners and admins shall each be able to log in and see only the screens for their role. |
| System-Level Requirement | The system shall provide authentication with two roles, Learner and Admin. Admin pages and admin API endpoints shall be inaccessible to accounts without the Admin role; the check is made by the server, not only hidden in the interface. |
| Primary User(s) | Learner, Admin |
| Priority | Must |
| Acceptance Criteria | A non-admin account cannot open an admin page or call an admin endpoint, and each role sees its own screens after login. |

### FR-005 - Evaluate Figure Retrieval

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-005 |
| Title | Evaluate Figure Retrieval |
| User-Level Requirement | The team shall be able to demonstrate that the diagram returned for a question is the correct one. |
| System-Level Requirement | The team shall build an evaluation set of at least 50 questions, each with the correct expected figure identified by handbook and printed page. Figure-retrieval results shall be scored using human-judged relevance, not text-retrieval metrics alone, with the metrics defined in 5.3. The team shall measure caption-binding accuracy from a manual sample and confirm, for a sample of returned figures, that the cited page matches the page the figure actually appears on. All metrics are measured before and after one deliberate retrieval improvement on the same set. |
| Primary User(s) | Admin / development team |
| Priority | Must |
| Acceptance Criteria | A committed 50+ question evaluation set exists with human-judged figure relevance scores, a measured caption-binding accuracy, and a measured provenance (page) correctness rate, reported in EVALUATION.md before and after the improvement. |

### FR-006 - View Coverage Map

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-006 |
| Title | View Coverage Map |
| User-Level Requirement | The admin shall be able to see which handbooks and chapters are covered and how well their figures were extracted. |
| System-Level Requirement | The system shall display, for each ingested handbook and each of its chapters, the number of pages processed, figures extracted, figures with a bound caption, and figures flagged as incorrect. The admin shall be able to open a chapter to list its figures. |
| Primary User(s) | Admin |
| Priority | Must |
| Acceptance Criteria | After a handbook is ingested, the coverage page shows per-chapter counts consistent with the ingestion report, and a chapter can be opened to list its figures. |

### FR-007 - Monitor Usage and Failures

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-007 |
| Title | Monitor Usage and Failures |
| User-Level Requirement | The admin shall be able to see how the system is used and where it fails. |
| System-Level Requirement | The system shall record, for every question asked, its time, its latency and its outcome (answered, low confidence, no answer found, or error). For a period chosen by the admin, the system shall display the query volume, the latency, the failure rate (questions ending in an error) and the list of questions for which no answer was found. |
| Primary User(s) | Admin |
| Priority | Must |
| Acceptance Criteria | After a set of test questions that includes unanswerable ones, the analytics page shows the correct number of queries, their latency, the failure rate, and lists the unanswered questions. |

### FR-008 - Re-index Content

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-008 |
| Title | Re-index Content |
| User-Level Requirement | The admin shall be able to rebuild the search content after corrections or changes. |
| System-Level Requirement | The system shall allow the admin to start re-indexing for one handbook or for the whole corpus, and shall show the outcome (success or failure) once it ends. If re-indexing fails, the previous index stays active. |
| Primary User(s) | Admin |
| Priority | Should |
| Acceptance Criteria | After re-indexing a handbook, a search returns results from the rebuilt content and the admin sees the outcome of the operation. |

### FR-009 - Answer with Cited Sources

| Field | Requirement Description |
| --- | --- |
| Requirement ID | FR-009 |
| Title | Answer with Cited Sources |
| User-Level Requirement | The learner shall be able to see where every statement in a written answer comes from. |
| System-Level Requirement | When the system writes an answer, it shall give the language model only the retrieved passages, and each sentence of the answer shall cite the passage it comes from (handbook and page). A sentence without a citation shall not be shown. Every number in the answer shall appear in a cited passage (BR-004); an automated test checks this. |
| Primary User(s) | Learner |
| Priority | Must |
| Acceptance Criteria | Each sentence of a displayed answer links to a retrieved passage, and the automated numeric check passes on the evaluation set. |

## 4. Non-Functional Requirements

### NFR-001 - Mobile Usability

| Field | Requirement Description |
| --- | --- |
| Requirement ID | NFR-001 |
| Title | Mobile Usability |
| Category | Usability |
| User/Business-Level Requirement | Learners should be able to use the system comfortably on a phone with a slow connection. |
| System-Level Requirement | The system shall display a responsive layout on mobile screens and load an initial results page in under 5 seconds on a throttled 3G connection. Figures are first shown as compressed thumbnails; the full-size image loads on request. |
| Applies To | Whole system |
| Priority | Must |
| Verification Criteria | Manual test on a phone with the connection throttled to 3G speed. |

### NFR-002 - Public Deployment

| Field | Requirement Description |
| --- | --- |
| Requirement ID | NFR-002 |
| Title | Public Deployment |
| Category | Availability |
| User/Business-Level Requirement | The system shall be reachable online at all times. |
| System-Level Requirement | The system shall be deployed to a public URL, separate from any local development environment, with seeded data, before the defence. |
| Applies To | Whole system |
| Priority | Must |
| Verification Criteria | The deployed URL is checked reachable before the defence. |

## 5. Retrieval and Data Design

### 5.1 Chunking strategy and justification

**Text chunks.** FAA handbooks are organised as chapters, sections with headings, and paragraphs, and their prose refers to figures by number ("see Figure 4-12"). Text is therefore chunked by structure, not by a fixed token count:

1. Text is split at section headings; a chunk never crosses a section boundary.
2. Inside a section, whole paragraphs are grouped into a chunk up to a size cap; a paragraph is never split.
3. Each chunk stores the handbook, chapter, section heading, and the pages it covers. The section heading is prepended to the chunk text before embedding.
4. No overlap between chunks: paragraphs are complete units, and the prepended heading gives each chunk its context.

Justification:
- A paragraph is the unit that names a figure. Splitting it would separate the words a learner searches for from the figure reference, and the figure would no longer be found through that paragraph.
- Keeping chunks inside one section keeps each chunk on one topic, so a retrieved chunk is about the question rather than a mix of two neighbouring systems.
- Storing pages per chunk gives every returned passage page-level provenance (BR-002).

The size cap is not chosen in advance. In Week 2 the team measures the paragraph and section length distribution of the first handbook, sets the cap from it, and records the value and the measurement here.

**Measurement and decision (28/10/2026, FAA-H-8083-15B, `python ingestion/chunk_text.py measure`).** Body text (figures, captions, front matter, table of contents and index excluded): 577 sections, 2,730 paragraphs, 140,352 words. Paragraph length: median 41 words, 90th percentile 107, 99th percentile 174, maximum 324.

| Cap (words) | Chunks | Median chunk (words) | Paragraphs longer than the cap |
| --- | --- | --- | --- |
| 150 | 1,326 | 112 | 72 |
| **200 (chosen)** | **1,080** | **138.5** | **15** |
| 250 | 911 | 162 | 3 |

**Cap = 200 words.** A chunk then holds two to four whole paragraphs on one topic, and only 15 paragraphs (0.5 %) exceed the cap; each of these becomes a chunk of its own rather than being split. Consequence for the embedding model (2.5): 200 words is about 260 tokens and the longest paragraph about 420, so the model must accept at least 512 input tokens, or long chunks would be silently truncated.

Content covered: chapters 1–11, Appendix A, Appendix B and the Glossary (pages with a printed number such as 4-8, A-1, G-7). Not chunked: front matter, table of contents, Index, and dot-leader lists (e.g. the shorthand table in Appendix A), because they list page numbers or abbreviations rather than explain anything. Headings are recognised by font (Helvetica-Bold 12 pt, Helvetica-Bold 10 pt, Times-BoldItalic 11 pt) and never carry over into the next chapter.

**Figure documents.** Each figure is also a search item of its own. Its searchable text is its caption, the paragraphs that reference it, and its section heading. A figure can then be found by what the handbook says about it, not only by its short caption. The figure image itself may additionally be embedded with an image model for joint text–image retrieval; whether this is kept is decided by measurement (5.3).

### 5.2 Page numbering

Each page stores both its position in the PDF file and its printed page number (FAA handbooks use the chapter–page form, e.g. "4-12"). The printed page number is the one cited to learners, because it is the number they see in the handbook. The PDF position is used to open the original page (UC-07).

### 5.3 Evaluation metrics

| Metric | Definition |
| --- | --- |
| Figure relevance judgement | For each returned figure, a team member scores 2 = the expected figure, 1 = a related but not the expected figure, 0 = not relevant. |
| Figure Hit@1 / Hit@5 | Share of answerable questions where a figure scored 2 is ranked first / in the top 5. |
| Figure MRR | Mean of 1 / rank of the first figure scored 2 (0 if none in the top 5). |
| No-answer accuracy | Share of the unanswerable questions in the set for which the system returns "no answer found". |
| Caption-binding accuracy | On a random sample of extracted figures, share whose stored caption is the correct caption. |
| Provenance correctness | On a random sample of returned figures, share whose cited printed page is the page the figure appears on. |

Sample sizes, the random seed used to draw samples, and all results are recorded in EVALUATION.md.

## 6. Appendices

### 6.1 Use Cases

| ID | Actor | Use case and main flow | Requirement |
| --- | --- | --- | --- |
| UC-01 | Admin | Load a handbook. The admin starts ingestion for an FAA handbook; the system downloads the PDF, extracts text and figures, binds each figure to its caption and referencing paragraph, tags it, records the licence, and stores everything in the database. | FR-001 |
| UC-02 | Learner | Ask a question. The learner types a topic or symptom; the system searches text and figures together and shows the procedure text with the correct diagram, handbook name and page number, or a clear "no answer found" message. | FR-002, FR-009 |
| UC-03 | Learner | Flag a wrong figure. The learner marks a returned figure as incorrect; it is added to the admin review queue. | FR-003 |
| UC-04 | Admin | Review and correct figures. The admin opens the review queue, checks a flagged figure against the handbook page, corrects its caption, page or reference link (or removes it), and views handbook and chapter coverage. | FR-003 |
| UC-05 | Learner, Admin | Log in. A user signs in and sees only the screens allowed for their role. | FR-004 |
| UC-06 | Development team | Evaluate figure retrieval. The team runs the 50+ question evaluation set, records human relevance judgements, and measures caption-binding and page-citation accuracy. | FR-005 |
| UC-07 | Learner | Verify a source. The learner opens a returned figure, sees it enlarged with caption, handbook and page, and compares it with an image of the original handbook page. | FR-002 |
| UC-08 | Admin | View the coverage map. The admin sees, per handbook and chapter, pages processed, figures extracted, captions bound and figures flagged. | FR-006 |
| UC-09 | Admin | Monitor usage. The admin sees query volume, latency, failure rate and the questions the system could not answer. | FR-007 |
| UC-10 | Admin | Re-index the corpus. The admin rebuilds the search content for one handbook or the whole corpus after corrections or a retrieval change. | FR-008 |

#### 6.1.1 Detailed use case descriptions

##### UC-01 - Load a handbook

| Field | Use Case Description |
| --- | --- |
| Primary actor | Admin (secondary: FAA website, embedding service) |
| Requirement | FR-001; BR-001, BR-005 |
| Preconditions | Admin is logged in. The handbook is listed on the FAA handbooks index (or is another source approved by the supervisor). |
| Trigger | Admin chooses "Add handbook" on the ingestion page. |
| Main flow | 1. Admin selects a handbook from the FAA index (or enters its PDF URL). 2. System reads the file size and shows it to the admin, who confirms (several handbooks exceed 100 MB). 3. System downloads the PDF and checks that it is a valid PDF. 4. System records the source URL, licence and retrieval date. 5. System extracts the text of each page, its printed page number, and the figures. 6. System detects each caption and figure number and binds every figure to its caption and to the page it appears on. 7. System finds the paragraphs that reference each figure and links them to it. 8. System tags each figure (at least figure number and chapter). 9. System chunks the text (5.1) and makes the content searchable (embeddings stored in the database). 10. System shows an ingestion report: pages processed, figures extracted, captions bound, figures without caption. |
| Alternative / exception flows | A1. URL unreachable or file is not a valid PDF: the system shows the error and stores nothing. A2. Licence cannot be determined: the document is not made searchable until the admin supplies it (BR-001). A3. A figure has no detectable caption: it is stored as "unbound" and added to the QA queue (UC-04). A4. Ingestion fails part-way: status is "Failed", partial content is not searchable, the admin can retry. A5. The document was already ingested: the system asks whether to cancel or re-ingest. |
| Postconditions | The document, its pages, text, figures, captions, references and licence are stored and searchable, and the report is available to the admin. |

##### UC-02 - Ask a question

| Field | Use Case Description |
| --- | --- |
| Primary actor | Learner (secondary: embedding / language model service) |
| Requirement | FR-002, FR-009; NFR-001; BR-002, BR-004 |
| Preconditions | Learner (or Admin) is logged in. At least one handbook has been ingested. |
| Trigger | Learner opens the search page and submits a topic or symptom. |
| Main flow | 1. Learner opens the search page, usually on a phone. 2. Learner types a topic or symptom and submits. 3. System searches the stored text and figures together. 4. System selects the best matching passages and figures. 5. System displays the procedure or explanation text, taken from retrieved sources only, with a citation on each sentence. 6. System displays the actual figure image (not a description of it) with its caption, handbook name and page number. 7. Learner reads the result and may zoom into the figure, verify the source (UC-07) or flag the figure (UC-03). |
| Alternative / exception flows | A1. No adequate match: the system states clearly that no answer was found and shows no weak match; the question is recorded as unanswered. A2. Empty query: the system asks the learner to enter a question. A3. Low confidence: the system shows the result with a visible low-confidence notice (FR-002). A4. Slow connection: text appears first and figures load progressively with a placeholder (NFR-001). A5. Internal error: the system shows a clear error message; the failure is logged. |
| Postconditions | The learner has seen text, figure and provenance (or a no-answer message). The query, its latency and its outcome are logged for analytics (UC-09). |

##### UC-03 - Flag a wrong figure

| Field | Use Case Description |
| --- | --- |
| Primary actor | Learner |
| Requirement | FR-003 |
| Preconditions | A result containing a figure is displayed to a logged-in learner. |
| Trigger | Learner selects "Wrong figure" on a returned figure. |
| Main flow | 1. Learner selects "Wrong figure" on the figure. 2. Learner optionally gives a short reason. 3. System stores the flag with the figure, the query, the user and the time. 4. System adds the figure to the admin QA queue. 5. System confirms to the learner that the figure was reported. |
| Alternative / exception flows | A1. The learner already flagged this figure for the same query: no duplicate entry is created. A2. Session expired: the learner is asked to log in again, then the flag is saved. |
| Postconditions | The figure appears in the QA queue with status "open". |

##### UC-04 - Review and correct figures

| Field | Use Case Description |
| --- | --- |
| Primary actor | Admin |
| Requirement | FR-003 |
| Preconditions | Admin is logged in. The QA queue contains figures flagged by a learner or by low search confidence, or unbound figures from ingestion. |
| Trigger | Admin opens the QA queue. |
| Main flow | 1. Admin opens the QA queue, which can be filtered by reason, handbook and status. 2. Admin selects an item; the system shows the figure, its caption, page, referencing paragraph and the query that triggered the flag. 3. Admin opens the original handbook page and compares it with the stored data. 4. Admin chooses an action: confirm as correct, correct the caption, page or reference link, edit tags, or remove the figure. 5. System saves the change, records who made it and when, and marks the item "resolved". 6. System updates the search content for that figure so that later searches use the correction. |
| Alternative / exception flows | A1. Admin cannot decide: the item stays open with a note. A2. Figure removed: it is excluded from all later searches. The figure is kept as a hidden record (not permanently deleted) so the audit trail remains complete, and the admin can restore it. A3. Queue is empty: the system says so. |
| Postconditions | The correction is stored and visible in a later search; the item is closed with an audit trail. |

##### UC-05 - Log in and log out

| Field | Use Case Description |
| --- | --- |
| Primary actor | Learner, Admin (also: unauthenticated visitor) |
| Requirement | FR-004; BR-003 |
| Preconditions | The user has an account. |
| Trigger | User opens the public URL. |
| Main flow | 1. System shows the login page. 2. User enters credentials and submits. 3. System authenticates the user and determines the role. 4. System redirects a Learner to the search page and an Admin to the admin dashboard. 5. System shows only the menu entries allowed for that role. 6. User logs out; the system ends the session and returns to the login page. |
| Alternative / exception flows | A1. Wrong credentials: a generic error is shown and no access is granted. A2. A Learner opens an admin page by its address or calls an admin endpoint directly: access is denied and no admin data is returned (BR-003). A3. Session expired: the user is sent to the login page. |
| Postconditions | An authenticated session with the right role exists (or has been closed). |

##### UC-06 - Evaluate figure retrieval

| Field | Use Case Description |
| --- | --- |
| Primary actor | Development team |
| Requirement | FR-005 |
| Preconditions | At least one handbook is ingested. The evaluation set has been written and committed. |
| Trigger | The team runs the evaluation procedure. |
| Main flow | 1. The team writes 50 or more questions, each with the expected figure (handbook and printed page) and the relevant text, plus a few questions with no answer in the corpus, and commits the set early. 2. The team runs every question and the system returns ranked figures. 3. The team records a human relevance judgement for each returned figure (5.3). 4. The team computes the figure-retrieval metrics from these judgements. 5. The team draws a manual sample of figures and checks each caption binding; caption-binding accuracy is computed. 6. The team draws a sample of returned figures and checks that the cited page is the page where the figure appears; the provenance correctness rate is computed. 7. Results are recorded in EVALUATION.md. 8. After the deliberate retrieval improvement, the same set is run again and both results are reported. |
| Alternative / exception flows | A1. The expected figure is not in the ingested corpus: the question is corrected or replaced, and the change is noted in EVALUATION.md. A2. The improvement lowers a result: it is reported as measured and explained, not hidden. |
| Postconditions | Measured figure-retrieval relevance, caption-binding accuracy and provenance correctness are documented, before and after the improvement. |

##### UC-07 - Verify a source

| Field | Use Case Description |
| --- | --- |
| Primary actor | Learner |
| Requirement | FR-002; BR-002 |
| Preconditions | A result with a figure is displayed. |
| Trigger | Learner selects the figure or "View source". |
| Main flow | 1. Learner selects the figure or "View source". 2. System shows the figure enlarged with its caption, handbook name and page number. 3. System shows an image of the original handbook page, rendered and stored at ingestion, so it can be compared with the figure; a link opens the FAA PDF at that page. 4. Learner compares and returns to the results (or flags the figure, UC-03). |
| Alternative / exception flows | A1. Original page unavailable: the system still shows the handbook name and page number and tells the learner the page could not be loaded. |
| Postconditions | The learner has checked the figure against its source. |

##### UC-08 - View the coverage map

| Field | Use Case Description |
| --- | --- |
| Primary actor | Admin |
| Requirement | FR-006; BR-003 |
| Preconditions | Admin is logged in. |
| Trigger | Admin opens the "Coverage" page. |
| Main flow | 1. System lists every ingested handbook with its chapters. 2. For each chapter the system shows pages processed, figures extracted, figures with a bound caption and figures flagged. 3. Admin spots gaps (e.g. a chapter with no figures, or many unbound figures). 4. Admin opens a chapter to see its figures; problem figures lead to UC-04. |
| Alternative / exception flows | A1. No handbook ingested: the page invites the admin to load one (UC-01). |
| Postconditions | The admin knows which parts of the corpus are covered and which need attention. |

##### UC-09 - Monitor usage and unanswered questions

| Field | Use Case Description |
| --- | --- |
| Primary actor | Admin |
| Requirement | FR-007; BR-003 |
| Preconditions | Admin is logged in. Queries have been logged. |
| Trigger | Admin opens the "Analytics" page. |
| Main flow | 1. Admin selects a period. 2. System shows query volume, latency, failure rate and the list of questions the system could not answer. 3. Admin opens an unanswered or failed question to see what happened. 4. Admin decides on an action: load another handbook (UC-01), review figures (UC-04) or note a retrieval problem for improvement. |
| Alternative / exception flows | A1. No queries in the period: the page shows an empty state. |
| Postconditions | The admin has an up-to-date view of how the system is used and where it fails. |

##### UC-10 - Re-index the corpus

| Field | Use Case Description |
| --- | --- |
| Primary actor | Admin (secondary: embedding service) |
| Requirement | FR-008 |
| Preconditions | Admin is logged in. At least one handbook is ingested. |
| Trigger | Admin selects "Re-index" for one handbook or for the whole corpus (e.g. after corrections or after a retrieval change). |
| Main flow | 1. Admin selects the scope and starts re-indexing. 2. System rebuilds the search content from the stored text, figures and corrections and shows progress. 3. On completion the new index replaces the old one and the system shows a summary. |
| Alternative / exception flows | A1. Re-indexing fails: the previous index stays active and the error is shown. |
| Postconditions | Searches use the rebuilt index. |

### 6.2 Diagrams

Diagram files are stored in `docs/diagrams/`.

- Figure 1 - Ingestion pipeline (FR-001)
- Figure 2 - Question answering and review flow (FR-002, FR-003)
- Figure 3 - Use case diagram: actors and use cases UC-01 to UC-10 (see 2.3.1 and 6.1)

### 6.3 Business Rules

| Rule ID | Business Rule |
| --- | --- |
| BR-001 | The licence, source URL and retrieval date of every ingested document must be recorded at ingestion time. |
| BR-002 | A figure may be shown to a learner only with its handbook name and the page it appears on. |
| BR-003 | Only accounts with the Admin role may load handbooks, correct figures or view analytics. |
| BR-004 | Any factual or numeric value in an answer must come from a retrieved source, never be generated by the model. |
| BR-005 | Only the sources provided in the project brief (FAA handbooks; optionally NASA NTRS and PubMed Central Open Access) are used; no other corpus is substituted without approval. |

### 6.4 Supporting References

- ESIB-USJ Project P7 brief (Technical training assistant).
- FAA handbooks and manuals index: <https://www.faa.gov/regulations_policies/handbooks_manuals/aviation> (primary corpus).
- NASA NTRS API: <https://ntrs.nasa.gov/api/citations/search> (optional stretch corpus).
- PubMed Central Open Access, S3 bucket `pmc-oa-opendata`, us-east-1 (optional stretch corpus; licence read per article).
