// The admin screens (P7-36; brief section 6, week 5 of the brief's plan).
//
// Each page is described here once: what it is for, which requirement it implements, what an
// operator will be able to do there, and what the empty page says until its own ticket is done.
// The brief warns that the admin side must let "a person who did not build this system" run it,
// so even the empty pages explain themselves instead of showing a blank table.
export const ADMIN_PAGES = [
  {
    path: "/admin/ingestion",
    title: "Ingestion",
    requirement: "FR-001, FR-008 · UC-01, UC-10 · BR-001",
    purpose: "Load an FAA handbook into the system and check that its figures were extracted correctly.",
    willDo: [
      "Add a handbook from the FAA index or from its PDF address, after seeing its size",
      "Read the ingestion report: pages processed, figures extracted, captions bound, figures without caption",
      "See the licence, source address and retrieval date recorded for each handbook",
      "Re-index one handbook or the whole corpus after corrections",
    ],
    empty: "No ingestion runs to show yet. For now, handbooks are loaded from the command line (ingestion/load_db.py).",
  },
  {
    path: "/admin/qa",
    title: "QA queue",
    requirement: "FR-003 · UC-03, UC-04",
    purpose: "Review figures that a learner flagged as wrong, that matched with low confidence, or that have no caption.",
    willDo: [
      "Filter the queue by reason, handbook and status",
      "Compare a figure with the original handbook page",
      "Correct its caption, page or reference, edit its tags, or remove it",
      "See who changed what and when",
    ],
    empty: "The queue is not connected yet. Flagged and unbound figures will appear here.",
  },
  {
    path: "/admin/coverage",
    title: "Coverage",
    requirement: "FR-006 · UC-08",
    purpose: "See which handbooks and chapters are covered, and how well their figures were extracted.",
    willDo: [
      "For each handbook and chapter: pages processed, figures extracted, captions bound, figures flagged",
      "Spot gaps, such as a chapter with no figures or many unbound ones",
      "Open a chapter to list its figures and send problem figures to the QA queue",
    ],
    empty: "Coverage is not computed yet. Two handbooks are loaded: FAA-H-8083-15B and FAA-H-8083-25C.",
  },
  {
    path: "/admin/analytics",
    title: "Analytics",
    requirement: "FR-007 · UC-09",
    purpose: "See how the system is used and where it fails.",
    willDo: [
      "Choose a period",
      "See the number of questions, their latency and the failure rate",
      "List the questions the system could not answer, and open one to see what happened",
    ],
    empty: "Charts are not built yet. Every question is already recorded in the query log (P7-28), so the history will be there.",
  },
];
