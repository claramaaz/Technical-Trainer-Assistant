import { useState } from "react";

// The written answer above the figure (UC-02 step 5; FR-002; BR-004).
//
// GET /answer returns answer.mode:
//   "llm"         sentences written by the LLM from the retrieved passages only, each one cited
//   "extractive"  the LLM was not used or failed: the passages are quoted word for word
//   "no_answer"   handled by App.jsx (no answer block, no figures)
// Each sentence lists the figures it comes from; a citation is a link to that figure on the page.
//
// In "extractive" mode the server quotes EVERY sentence of all the returned passages, which is
// far too long to read. The page then shows only the sentences about the main figure, the first
// QUOTED_SHOWN of them, with a button for the rest.
const QUOTED_SHOWN = 3;

export default function AnswerText({ answer, results, onShowFigure }) {
  const [expanded, setExpanded] = useState(false);
  const byId = new Map(results.map((r) => [r.id, r]));
  const quoted = answer.mode === "extractive";

  let sentences = answer.sentences;
  if (quoted) {
    const aboutMain = sentences.filter((s) => s.citations.includes(results[0].id));
    if (aboutMain.length > 0) sentences = aboutMain;
  }
  const hidden = quoted && !expanded ? Math.max(0, sentences.length - QUOTED_SHOWN) : 0;
  const shown = hidden > 0 ? sentences.slice(0, QUOTED_SHOWN) : sentences;

  return (
    <section className="answer" aria-label="Answer">
      <h2 className="answer-title">{quoted ? "From the handbook" : "Answer"}</h2>
      {quoted && (
        <p className="answer-note">
          Quoted word for word from the handbook passage of the figure below (no summary was written).
        </p>
      )}
      <ul className="answer-sentences">
        {shown.map((s, i) => (
          <li key={i}>
            {s.text}{" "}
            {s.citations
              .filter((id) => byId.has(id))
              .map((id) => (
                <button
                  key={id}
                  type="button"
                  className="cite"
                  onClick={() => onShowFigure(id)}
                  title={`${byId.get(id).handbook}, page ${byId.get(id).printed_page}`}
                >
                  Fig. {byId.get(id).figure_id || "?"}
                </button>
              ))}
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <button type="button" className="answer-more" onClick={() => setExpanded(true)}>
          Show {hidden} more sentence{hidden > 1 ? "s" : ""}
        </button>
      )}
    </section>
  );
}
