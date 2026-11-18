import { useState } from "react";

// The written answer (UC-02 step 5; FR-009; BR-004).
//   "llm"         sentences written by the language model from the retrieved passages only; every
//                 sentence cites the figure passages it comes from (a sentence without a citation is
//                 never shown, the server drops it)
//   "extractive"  the language model was not used or failed: the passages are quoted word for word
// A citation is a button: it opens that figure with its source page (UC-07).
//
// In "extractive" mode the server quotes every sentence of the returned passages, which is too long
// to read on a phone: only the sentences about the main figure are kept, QUOTED_SHOWN at first.
const QUOTED_SHOWN = 3;
// The language model sometimes copies the passage ids it was given into the sentence ("... drag. [55]").
// They mean nothing to a learner (the Fig. chips already show the source), so they are removed.
const ID_MARKERS = /\s*\[(?:\d+\s*,?\s*)+\]/g;
const clean = (text) => text.replace(ID_MARKERS, "").trim();

export default function AnswerText({ answer, results, onOpenSource }) {
  const [expanded, setExpanded] = useState(false);
  const byId = new Map(results.map((r) => [r.id, r]));
  const quoted = answer.mode === "extractive";

  let sentences = answer.sentences || [];
  if (quoted && results[0]) {
    const aboutMain = sentences.filter((s) => s.citations.includes(results[0].id));
    if (aboutMain.length > 0) sentences = aboutMain;
  }
  const hidden = quoted && !expanded ? Math.max(0, sentences.length - QUOTED_SHOWN) : 0;
  const shown = hidden > 0 ? sentences.slice(0, QUOTED_SHOWN) : sentences;
  if (shown.length === 0) return null;

  const cites = (s) =>
    s.citations
      .filter((id) => byId.has(id))
      .map((id) => {
        const r = byId.get(id);
        return (
          <button
            key={id}
            type="button"
            className="cite"
            onClick={() => onOpenSource(r)}
            title={`${r.handbook}, page ${r.printed_page}`}
          >
            Fig. {r.figure_id || "?"}
          </button>
        );
      });

  if (!quoted) {
    return (
      <div className="answer-text">
        <p>
          {shown.map((s, i) => (
            <span key={i}>
              {clean(s.text)} {cites(s)}{" "}
            </span>
          ))}
        </p>
      </div>
    );
  }

  return (
    <div className="answer-text answer-quoted">
      <p className="answer-note">Quoted word for word from the handbook (no summary could be written this time).</p>
      <ul>
        {shown.map((s, i) => (
          <li key={i}>
            {clean(s.text)} {cites(s)}
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <button type="button" className="btn-text" onClick={() => setExpanded(true)}>
          Show {hidden} more sentence{hidden > 1 ? "s" : ""}
        </button>
      )}
    </div>
  );
}
