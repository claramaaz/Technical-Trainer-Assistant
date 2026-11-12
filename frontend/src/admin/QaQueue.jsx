import { useEffect, useState } from "react";

// QA queue page (P7-38 fills it; P7-36 made the empty layout). Lists the figures learners
// reported with "Wrong figure" (GET /admin/flags, Admins only). Correcting or closing a report
// is UC-04, a later ticket: this page only shows what is waiting.
export default function QaQueue({ page, onSessionExpired }) {
  const [state, setState] = useState("loading"); // loading | ready | error
  const [reports, setReports] = useState([]);

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
      <h1>{page.title}</h1>
      <p className="admin-lead">{page.purpose}</p>

      {state === "loading" && <p className="qa-note">Loading reports…</p>}
      {state === "error" && (
        <p className="qa-note admin-denied" role="alert">
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
                  <a href={r.image_url} target="_blank" rel="noopener noreferrer">
                    Open full-size figure
                  </a>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

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
