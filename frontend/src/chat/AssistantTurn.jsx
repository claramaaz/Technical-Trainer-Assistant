import { useState } from "react";
import { LogoMark } from "../Logo.jsx";
import AnswerText from "./AnswerText.jsx";
import { Caption } from "./caption.jsx";
import FigurePlate from "./FigurePlate.jsx";
import Rating from "./Rating.jsx";

export const NO_ANSWER = "No adequate answer was found in the handbooks.";
// FR-002 / brief section 12: a weak match is shown, but never presented as a sure one.
const LOW_CONFIDENCE = "This answer may not match your question well. Check the source before relying on it.";

// One answer of the assistant (UC-02, FR-009): low-confidence notice, written answer with its
// citations, the main figure in large (the figures cited by the answer come first, chat.py), the
// other returned figures folded away, up to 3 suggested follow-up questions, good / bad buttons.
// A "no answer" shows only the message: no weak figure (FR-002, UC-02 A1).
export default function AssistantTurn({ turn, onOpenSource, onAsk, busy, onRetry, onSessionExpired }) {
  const [othersOpen, setOthersOpen] = useState(false);

  if (turn.status === "loading") {
    return (
      <Assistant>
        <p className="loading-line pulse" role="status">Searching the handbooks and writing the answer…</p>
      </Assistant>
    );
  }
  if (turn.status === "error") {
    return (
      <Assistant>
        <p className="notice notice-error" role="alert">{turn.error}</p>
        <button type="button" className="btn btn-quiet btn-small" onClick={onRetry} disabled={busy}>
          Ask again
        </button>
      </Assistant>
    );
  }

  const data = turn.data;
  if (data.answer?.mode === "no_answer" || !data.results?.length) {
    return (
      <Assistant>
        <div className="no-answer" role="alert">
          <strong>{NO_ANSWER}</strong>
          <p>Try other words, or ask about a topic covered by the FAA handbooks.</p>
        </div>
        <Rating queryId={data.query_id} onSessionExpired={onSessionExpired} />
      </Assistant>
    );
  }

  const [main, ...others] = data.results;
  return (
    <Assistant>
      {data.confidence === "low" && (
        <p className="notice notice-warning" role="alert">
          <strong>Low confidence.</strong> {LOW_CONFIDENCE}
        </p>
      )}
      <AnswerText answer={data.answer} results={data.results} onOpenSource={onOpenSource} />
      <FigurePlate result={main} query={turn.message} onOpenSource={onOpenSource} onSessionExpired={onSessionExpired} />

      {others.length > 0 && (
        <div className="others">
          <button type="button" className="others-toggle" aria-expanded={othersOpen} onClick={() => setOthersOpen(!othersOpen)}>
            <span aria-hidden="true">{othersOpen ? "▾" : "▸"}</span> Other figures found ({others.length})
          </button>
          {othersOpen && (
            <ul className="others-list">
              {others.map((r) => (
                <li key={r.id}>
                  <button type="button" className="other" onClick={() => onOpenSource(r)}>
                    <img src={r.thumbnail_url || r.image_url} alt="" loading="lazy" decoding="async" />
                    <span className="other-text">
                      <span className="other-caption"><Caption caption={r.caption} figureNumber={r.figure_id} /></span>
                      <span className="plate-source">{r.handbook}, page {r.printed_page}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {data.follow_ups?.length > 0 && (
        <div className="follow-ups">
          <p className="follow-ups-title">Ask next</p>
          <ul>
            {data.follow_ups.map((q) => (
              <li key={q}>
                <button type="button" className="follow-up" onClick={() => onAsk(q)} disabled={busy}>
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <Rating queryId={data.query_id} onSessionExpired={onSessionExpired} />
    </Assistant>
  );
}

function Assistant({ children }) {
  return (
    <div className="turn-assistant">
      <span className="turn-avatar" aria-hidden="true"><LogoMark size={18} /></span>
      <div className="turn-body">{children}</div>
    </div>
  );
}
