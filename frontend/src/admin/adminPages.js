// The admin screens (P7-36; brief section 6), in the order of the sidebar.
//
// Each page is described here once: what it is for and which requirement it implements. A page whose
// ticket is not done yet shows what it will do, because the brief asks that "a person who did not
// build this system" can run the admin side: even an unfinished page explains itself.
export const ADMIN_PAGES = [
  {
    path: "/admin/sources",
    title: "Sources",
    requirement: "FR-001, FR-008 · UC-01, UC-10 · BR-001",
    purpose: "Load FAA handbooks, follow their ingestion, and re-index the search after a correction.",
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
    empty: "When a learner presses \"Wrong figure\" on an answer, the figure appears here with the question it was returned for.",
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
    empty: "Coverage is not computed yet. The Sources page already lists each handbook with its number of figures.",
  },
  {
    path: "/admin/analytics",
    title: "Analytics",
    requirement: "FR-007, FR-010 · UC-09",
    purpose: "See how much the assistant is used, how fast it answers, where it fails, and which answers learners rated bad.",
  },
];
