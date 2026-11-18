import { useState } from "react";
import { api } from "../api.js";

// Good / bad response buttons under an answer (P7-53; FR-010). The rating is stored with the
// answer's query_id (returned by POST /chat), the user and the time. Pressing the other button
// changes the rating (one rating per user and answer). Shown only when the answer has a query_id
// (none when the server could not write the query log).
export default function Rating({ queryId, onSessionExpired }) {
  const [rating, setRating] = useState(null);   // the saved rating: "good" | "bad" | null
  const [sending, setSending] = useState(null);
  const [error, setError] = useState("");

  if (!queryId) return null;

  async function rate(value) {
    if (value === rating || sending) return;
    setSending(value);
    setError("");
    try {
      await api("/ratings", { method: "POST", json: { query_id: queryId, rating: value }, onSessionExpired });
      setRating(value);
    } catch (e) {
      if (e.status !== 401) setError(e.status === 404 ? "This answer can no longer be rated." : "The rating was not saved. Try again.");
    } finally {
      setSending(null);
    }
  }

  return (
    <div className="rating" role="group" aria-label="Rate this answer">
      <span className="rating-q">{rating ? "Thanks for rating this answer." : "Was this answer useful?"}</span>
      <span className="rating-buttons">
      {["good", "bad"].map((value) => (
        <button
          key={value}
          type="button"
          className={`rating-btn rating-${value}`}
          aria-pressed={rating === value}
          disabled={sending !== null}
          onClick={() => rate(value)}
        >
          <Thumb down={value === "bad"} />
          {value === "good" ? "Good" : "Bad"}
        </button>
      ))}
      </span>
      {error && <span className="rating-error" role="alert">{error}</span>}
    </div>
  );
}

function Thumb({ down }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={down ? { transform: "scaleY(-1)" } : undefined}>
      <path d="M7 10v11H3V10z" />
      <path d="M7 10l4-8a3 3 0 0 1 3 3v4h6a2 2 0 0 1 2 2.3l-1.4 8A2 2 0 0 1 18.6 21H7" />
    </svg>
  );
}
