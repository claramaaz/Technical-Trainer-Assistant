import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import PageHead from "./PageHead.jsx";

// Sources panel (P7-40; FR-001, FR-008, UC-01, UC-10, BR-001).
//   - every handbook in the database: status, searchable or not, pages, figures, figures to review,
//     licence and source (BR-001)
//   - "Add a handbook": upload the PDF with its source URL, licence and retrieval date; the server
//     checks it and runs the ingestion in the background (POST /admin/documents -> 202 + job id)
//   - the ingestion and re-index jobs, followed every few seconds while one is queued or running:
//     step i of n, the extraction report, or the error of the failed step
//   - Re-index one handbook or all of them (POST /admin/reindex)
const POLL_MS = 3000;
const DEFAULT_LICENCE = "Public domain (U.S. Government work)";

export default function Sources({ page, onSessionExpired }) {
  const [data, setData] = useState(null);     // { documents, jobs }
  const [error, setError] = useState("");
  const [message, setMessage] = useState(null); // { kind: "info" | "error", text }
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      setData(await api("/admin/documents", { onSessionExpired }));
      setError("");
    } catch (e) {
      if (e.status !== 401) setError(e.message);
    }
  }, [onSessionExpired]);

  useEffect(() => {
    load();
  }, [load]);

  const active = data?.jobs?.some((j) => j.status === "queued" || j.status === "running");
  useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(load, POLL_MS);
    return () => clearInterval(timer);
  }, [active, load]);

  async function reindex(handbookId) {
    const what = handbookId === "ALL" ? "every handbook" : handbookId;
    if (!window.confirm(`Rebuild the search vectors of ${what}? The current index stays in use until the new one is ready.`)) return;
    setMessage(null);
    try {
      await api("/admin/reindex", { method: "POST", json: { handbook_id: handbookId }, onSessionExpired });
      setMessage({ kind: "info", text: `Re-index of ${what} started. Follow it in the jobs below.` });
      load();
    } catch (e) {
      if (e.status !== 401) setMessage({ kind: "error", text: e.message });
    }
  }

  return (
    <section className="admin-page">
      <PageHead page={page}>
        <div className="head-actions">
          <button type="button" className="btn" onClick={() => setAdding(!adding)} aria-expanded={adding}>
            {adding ? "Close" : "Add a handbook"}
          </button>
          <button type="button" className="btn btn-quiet" onClick={() => reindex("ALL")} disabled={!data?.documents?.length || active}>
            Re-index all
          </button>
        </div>
      </PageHead>

      {message && (
        <p className={`notice ${message.kind === "error" ? "notice-error" : "notice-info"}`} role="status">{message.text}</p>
      )}
      {adding && (
        <UploadForm
          onSessionExpired={onSessionExpired}
          onStarted={(id) => {
            setAdding(false);
            setMessage({ kind: "info", text: `${id} was uploaded. Its ingestion runs in the background; follow it below.` });
            load();
          }}
        />
      )}

      {error && <p className="notice notice-error" role="alert">{error}</p>}
      {!data && !error && <p className="loading-line">Loading the handbooks…</p>}

      {data && (
        <>
          <h2 className="admin-subtitle">Handbooks</h2>
          {data.documents.length === 0 ? (
            <div className="admin-empty"><strong>No handbook loaded yet.</strong> Add one to make it searchable.</div>
          ) : (
            <ul className="doc-list">
              {data.documents.map((d) => (
                <li key={d.id} className="doc">
                  <div className="doc-main">
                    <p className="doc-title">{d.title}</p>
                    <p className="doc-id">{d.id}</p>
                    <p className="doc-meta">
                      {d.licence ? d.licence : <strong className="text-danger">Licence missing, not searchable</strong>}
                      {d.retrieved_at && <>, retrieved {formatDate(d.retrieved_at)}</>}
                      {d.source_url && (
                        <>, <a href={d.source_url} target="_blank" rel="noopener noreferrer">source</a></>
                      )}
                    </p>
                  </div>
                  <dl className="doc-stats">
                    <div><dt>Status</dt><dd><StatusChip status={d.searchable ? "searchable" : d.status} /></dd></div>
                    <div><dt>Pages</dt><dd className="num">{d.pdf_pages ?? "–"}</dd></div>
                    <div><dt>Figures</dt><dd className="num">{d.figures}</dd></div>
                    <div><dt>To review</dt><dd className="num">{d.needs_review}</dd></div>
                  </dl>
                  <button type="button" className="btn btn-quiet btn-small" onClick={() => reindex(d.id)} disabled={active}>
                    Re-index
                  </button>
                </li>
              ))}
            </ul>
          )}

          <h2 className="admin-subtitle">Ingestion and re-index jobs</h2>
          {data.jobs.length === 0 ? (
            <p className="muted">No job yet. Uploading a handbook or re-indexing starts one.</p>
          ) : (
            <ul className="job-list">
              {data.jobs.map((j) => <Job key={j.id} job={j} />)}
            </ul>
          )}
        </>
      )}
      <p className="admin-req">Requirements: {page.requirement}</p>
    </section>
  );
}

function Job({ job }) {
  const running = job.status === "running" || job.status === "queued";
  const pct = job.steps_total ? Math.round((job.steps_done / job.steps_total) * 100) : 0;
  const report = job.report;
  return (
    <li className={`job job-${job.status}`}>
      <div className="job-head">
        <StatusChip status={job.status} />
        <span className="job-title">{job.title === "Re-index" ? `Re-index ${job.document_id === "ALL" ? "all handbooks" : job.document_id}` : `${job.document_id}, ${job.title}`}</span>
        <span className="job-time">{formatDateTime(job.created_at)}{job.email ? `, by ${job.email}` : ""}</span>
      </div>
      {running && (
        <div className="job-progress">
          <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={job.steps_total} aria-valuenow={job.steps_done}>
            <span style={{ width: `${pct}%` }} />
          </div>
          <span className="num">Step {Math.min(job.steps_done + 1, job.steps_total)} of {job.steps_total}{job.step ? `: ${job.step}` : ""}</span>
        </div>
      )}
      {job.status === "done" && job.finished_at && (
        <p className="job-line">Finished {formatDateTime(job.finished_at)}{job.figures ? `, ${job.figures} figures in the database` : ""}.</p>
      )}
      {job.status === "failed" && (
        <details className="job-error">
          <summary>Failed{job.step ? ` at "${job.step}"` : ""}. Show the error</summary>
          <pre>{job.error}</pre>
        </details>
      )}
      {report && (
        <dl className="job-report">
          <div><dt>PDF pages</dt><dd className="num">{report.pdf_pages}</dd></div>
          <div><dt>Captions found</dt><dd className="num">{report.captions_found}</dd></div>
          <div><dt>Figures bound to a caption</dt><dd className="num">{report.figures_bound_to_caption}</dd></div>
          <div><dt>Regions without caption</dt><dd className="num">{report.unbound_regions}</dd></div>
          <div><dt>Flagged for review</dt><dd className="num">{report.bound_figures_flagged_for_review}</dd></div>
        </dl>
      )}
    </li>
  );
}

const STATUS_LABELS = {
  searchable: "Searchable", loaded: "Loaded", queued: "Queued", running: "Running", done: "Done", failed: "Failed",
};

function StatusChip({ status }) {
  return <span className={`chip chip-${status}`}>{STATUS_LABELS[status] || status}</span>;
}

function UploadForm({ onStarted, onSessionExpired }) {
  const [file, setFile] = useState(null);
  const [fields, setFields] = useState({
    id: "", title: "", source_url: "https://www.faa.gov/regulations_policies/handbooks_manuals/aviation",
    licence: DEFAULT_LICENCE, retrieved_at: new Date().toISOString().slice(0, 10),
  });
  const [progress, setProgress] = useState(null); // 0..100 while uploading
  const [error, setError] = useState("");
  const xhr = useRef(null);

  const set = (name) => (e) => setFields({ ...fields, [name]: e.target.value });

  function pick(e) {
    const f = e.target.files?.[0] || null;
    setFile(f);
    // Suggest the id from the file name: "FAA-H-8083-3C.pdf" -> "FAA-H-8083-3C".
    if (f && !fields.id) setFields({ ...fields, id: f.name.replace(/\.pdf$/i, "") });
  }

  function submit(event) {
    event.preventDefault();
    if (!file) return setError("Choose the PDF file of the handbook.");
    setError("");
    const form = new FormData();
    form.append("file", file);
    Object.entries(fields).forEach(([k, v]) => form.append(k, v.trim()));
    // XMLHttpRequest instead of fetch: it reports the upload progress (handbooks are up to ~200 MB).
    const request = new XMLHttpRequest();
    xhr.current = request;
    request.open("POST", "/admin/documents");
    request.upload.onprogress = (e) => e.lengthComputable && setProgress(Math.round((e.loaded / e.total) * 100));
    request.onload = () => {
      setProgress(null);
      if (request.status === 401) return onSessionExpired?.();
      let body = null;
      try { body = JSON.parse(request.responseText); } catch { /* not JSON */ }
      if (request.status === 202) return onStarted(fields.id.trim());
      const detail = typeof body?.detail === "string" ? body.detail : `the server answered with an error (${request.status})`;
      setError(`The handbook was not added: ${detail}.`);
    };
    request.onerror = () => {
      setProgress(null);
      setError("Could not reach the server. Nothing was added; try again.");
    };
    setProgress(0);
    request.send(form);
  }

  useEffect(() => () => xhr.current?.abort(), []);
  const uploading = progress !== null;

  return (
    <form className="upload" onSubmit={submit}>
      <h2>Add a handbook</h2>
      <p className="muted">
        Upload the PDF from the FAA website. The source address, licence and retrieval date are required: a handbook
        with an unknown licence is never searchable (BR-001).
      </p>
      <div className="upload-grid">
        <label className="field upload-file">
          PDF file
          <input type="file" accept="application/pdf,.pdf" onChange={pick} disabled={uploading} required />
        </label>
        <label className="field">
          Handbook id
          <input value={fields.id} onChange={set("id")} placeholder="FAA-H-8083-3C" pattern="[A-Za-z0-9][A-Za-z0-9._\-]{2,59}" required disabled={uploading} />
          <span className="field-hint">Letters, digits, - _ or . as on the FAA cover</span>
        </label>
        <label className="field">
          Title
          <input value={fields.title} onChange={set("title")} placeholder="Airplane Flying Handbook" maxLength={300} required disabled={uploading} />
        </label>
        <label className="field">
          Source URL
          <input type="url" value={fields.source_url} onChange={set("source_url")} required disabled={uploading} />
        </label>
        <label className="field">
          Licence
          <input value={fields.licence} onChange={set("licence")} maxLength={300} required disabled={uploading} />
        </label>
        <label className="field">
          Retrieved on
          <input type="date" value={fields.retrieved_at} max={new Date().toISOString().slice(0, 10)} onChange={set("retrieved_at")} required disabled={uploading} />
        </label>
      </div>
      {error && <p className="notice notice-error" role="alert">{error}</p>}
      <div className="upload-actions">
        <button type="submit" className="btn" disabled={uploading}>{uploading ? "Uploading…" : "Upload and start ingestion"}</button>
        {uploading && (
          <span className="upload-progress">
            <span className="bar"><span style={{ width: `${progress}%` }} /></span>
            <span className="num">{progress}%</span>
          </span>
        )}
      </div>
    </form>
  );
}

function formatDate(value) {
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatDateTime(value) {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
}
