import { useEffect, useState } from "react";
import { api } from "../api.js";
import PageHead from "./PageHead.jsx";

// QA queue page (P7-38 fills it; P7-36 made the empty layout). Lists the figures learners
// reported with "Wrong figure" (GET /admin/flags, Admins only). After checking a figure, the Admin
// can dismiss the report when the figure was right (POST /admin/flags/{id}/dismiss, UC-04): it
// leaves the queue and is kept as resolved. A report never removed the figure from the answers.
// Correcting a figure (caption, page, removal) is a later ticket.
export default function QaQueue({ page, onSessionExpired }) {
  const [state, setState] = useState("loading"); // loading | ready | error
  const [reports, setReports] = useState([]);
  const [busy, setBusy] = useState(null);       // id of the report being dismissed
  const [message, setMessage] = useState(null); // { kind, text }

  async function dismiss(report, allForFigure) {
    setBusy(report.id);
    setMessage(null);
    try {
      const { count } = await api(`/admin/flags/${report.id}/dismiss`, {
        method: "POST", json: { all_for_figure: allForFigure }, onSessionExpired,
      });
      setReports((list) => list.filter((r) => (allForFigure ? r.figure_id !== report.figure_id : r.id !== report.id)));
      setMessage({ kind: "info", text: `${count} report${count > 1 ? "s" : ""} of Figure ${report.figure_number} dismissed. The figure stays in the answers.` });
    } catch (e) {
      if (e.status === 404) setReports((list) => list.filter((r) => r.id !== report.id));
      if (e.status !== 401) setMessage({ kind: "error", text: e.status === 404 ? "This report was already closed." : e.message });
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    fetch("/admin/flags")
      .then(async (r) => {
        if (cancelled) return;
        if (r.status === 401) return onSessionExpired?.();
        if (!r.ok) throw new Error(String(r.status));
        const data = await r.json();
        if (cancelled) return;
        setReports(data.flags);
        setState("ready");
      })
      .catch(() => !cancelled && setState("error"));
    return () => {
      cancelled = true;
    };
  }, [onSessionExpired]);

  return (
    <section className="admin-page">
      <PageHead page={page} />

      {message && (
        <p className={`notice ${message.kind === "error" ? "notice-error" : "notice-info"}`} role="status">{message.text}</p>
      )}
      {state === "loading" && <p className="qa-note">Loading reports…</p>}
      {state === "error" && (
        <p className="notice notice-error" role="alert">
          The reports could not be loaded. Try again later.
        </p>
      )}
      {state === "ready" && reports.length === 0 && (
        <div className="admin-empty" role="status">
          <strong>No open reports.</strong> {page.empty}
        </div>
      )}
      {state === "ready" && reports.length > 0 && (
        <>
          <p className="qa-note">
            {reports.length} open report{reports.length > 1 ? "s" : ""}, newest first
            {reports.length >= 200 ? " (only the 200 most recent are shown)" : ""}.
          </p>
          <ul className="qa-list">
            {reports.map((r) => (
              <li key={r.id} className="qa-item">
                <img
                  className="qa-thumb"
                  src={r.thumbnail_url || r.image_url}
                  alt={r.caption}
                  loading="lazy"
                />
                <div className="qa-body">
                  <p className="qa-source">
                    <span className="figure-number">Figure {r.figure_number}</span>
                    {r.handbook}, page {r.printed_page}
                  </p>
                  <p className="qa-caption">{r.caption}</p>
                  <p className="qa-line">
                    <span className="qa-label">Question:</span> {r.query}
                  </p>
                  <p className="qa-line">
                    <span className="qa-label">Reason:</span>{" "}
                    {r.reason || <em>no reason given</em>}
                  </p>
                  <p className="qa-meta">
                    Reported by {r.reported_by} · {new Date(r.flagged_at).toLocaleString()}
                    {r.reports_for_figure > 1 &&
                      ` · ${r.reports_for_figure} open reports for this figure`}
                  </p>
                  <div className="qa-actions">
                    <a href={r.image_url} target="_blank" rel="noopener noreferrer">
                      Open full-size figure
                    </a>
                    <button type="button" className="btn btn-quiet btn-small" disabled={busy !== null}
                      onClick={() => dismiss(r, false)}
                      title="The figure is right: close this report. The figure stays in the answers.">
                      {busy === r.id ? "Dismissing…" : "Dismiss report"}
                    </button>
                    {r.reports_for_figure > 1 && (
                      <button type="button" className="btn-text" disabled={busy !== null} onClick={() => dismiss(r, true)}>
                        Dismiss all {r.reports_for_figure} reports of this figure
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="qa-note qa-help">
        A report only puts the figure in this queue: the figure keeps appearing in answers. Dismiss a report
        when you checked the figure and it is right.
      </p>
      <h2 className="admin-subtitle">Coming next (UC-04)</h2>
      <ul className="admin-list">
        {page.willDo.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <p className="admin-req">Requirements: {page.requirement}</p>
    </section>
  );
}
