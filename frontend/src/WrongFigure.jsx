import { useState } from "react";
import "./WrongFigure.css";

// "Wrong figure" under a search result (P7-38; FR-003, UC-03).
//
// 1. The learner presses "Wrong figure".  2. An optional reason can be typed.
// 3. The server stores the report with the figure, the question, the user and the time,
//    and the figure appears in the admin QA queue.  4. The learner sees a confirmation.
// A second report of the same figure for the same question is not stored twice (UC-03 A1);
// the server answers "already reported" and the page says so.
//
// Known limitation (UC-03 A2): if the session has expired, the learner is sent to the login
// page and the report is NOT sent automatically afterwards; it has to be made again.
export default function WrongFigure({ figureId, query, onSessionExpired }) {
  // idle | open | sending | reported | already | error
  const [state, setState] = useState("idle");
  const [reason, setReason] = useState("");
  const [errorText, setErrorText] = useState("");

  async function send(event) {
    event.preventDefault();
    setState("sending");
    try {
      const response = await fetch("/flags", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ figure_id: figureId, query, reason: reason.trim() || null }),
      });
      if (response.status === 401) {
        onSessionExpired?.();
        return;
      }
      if (response.status === 201) return setState("reported");
      if (response.status === 200) return setState("already");
      throw new Error(
        response.status === 404
          ? "This figure is no longer available."
          : `The report could not be saved (error ${response.status}).`
      );
    } catch (error) {
      setErrorText(
        error instanceof TypeError
          ? "Could not reach the server. Your report was not sent; try again."
          : error.message
      );
      setState("error");
    }
  }

  if (state === "reported")
    return (
      <p className="flag-done" role="status">
        Thanks. This figure was reported and will be checked by an admin.
      </p>
    );
  if (state === "already")
    return (
      <p className="flag-done" role="status">
        You already reported this figure for this question.
      </p>
    );
  if (state === "idle")
    return (
      <button type="button" className="flag-button" onClick={() => setState("open")}>
        Wrong figure
      </button>
    );

  const sending = state === "sending";
  const fieldId = `flag-reason-${figureId}`;
  return (
    <form className="flag-form" onSubmit={send}>
      <label htmlFor={fieldId}>What is wrong with this figure? (optional)</label>
      <textarea
        id={fieldId}
        rows={2}
        maxLength={500}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="e.g. it shows a different instrument"
        disabled={sending}
      />
      {state === "error" && (
        <p className="flag-error" role="alert">
          {errorText}
        </p>
      )}
      <div className="flag-actions">
        <button type="submit" className="flag-send" disabled={sending}>
          {sending ? "Sending…" : "Report figure"}
        </button>
        <button
          type="button"
          className="flag-cancel"
          disabled={sending}
          onClick={() => {
            setReason("");
            setState("idle");
          }}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
