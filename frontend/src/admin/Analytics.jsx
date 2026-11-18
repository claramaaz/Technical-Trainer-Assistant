import { useEffect, useState } from "react";
import { api } from "../api.js";
import PageHead from "./PageHead.jsx";

// Analytics page (P7-43; FR-007, UC-09, FR-010). Reads GET /admin/analytics?from=&to=.
//   1. The admin picks a period (UC-09 step 1). Days are UTC days, as in the query log.
//   2. Questions, failure rate (questions ending in an error, FR-007), questions with no answer,
//      latency, and the good / bad ratings (FR-010) (step 2).
//   3. Questions per day, as bars, with the same numbers as a table.
//   4. The questions with no answer and the failed ones, each opening on what happened (step 3),
//      and the answers rated bad with their question (FR-010).
//   A1: no question in the period -> an empty state.
const PRESETS = [
  { key: "today", label: "Today", days: 1 },
  { key: "7", label: "Last 7 days", days: 7 },
  { key: "30", label: "Last 30 days", days: 30 },
];

function utcDay(offset = 0) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offset);
  return d.toISOString().slice(0, 10);
}

export default function Analytics({ page, onSessionExpired }) {
  const [preset, setPreset] = useState("7");
  const [custom, setCustom] = useState({ from: utcDay(-6), to: utcDay() });
  const [state, setState] = useState({ status: "loading" });

  const period = (() => {
    const p = PRESETS.find((x) => x.key === preset);
    return p ? { from: utcDay(-(p.days - 1)), to: utcDay() } : custom;
  })();

  useEffect(() => {
    const controller = new AbortController();
    setState((s) => ({ ...s, status: "loading" }));
    api(`/admin/analytics?from=${period.from}&to=${period.to}`, { signal: controller.signal, onSessionExpired })
      .then((data) => setState({ status: "ready", data }))
      .catch((e) => {
        if (e.name !== "AbortError" && e.status !== 401) setState({ status: "error", error: e.message });
      });
    return () => controller.abort();
  }, [period.from, period.to, onSessionExpired]);

  const data = state.data;
  return (
    <section className="admin-page">
      <PageHead page={page} />

      <div className="period" role="group" aria-label="Period">
        <div className="segmented">
          {[...PRESETS, { key: "custom", label: "Custom" }].map((p) => (
            <button key={p.key} type="button" aria-pressed={preset === p.key} onClick={() => setPreset(p.key)}>
              {p.label}
            </button>
          ))}
        </div>
        {preset === "custom" && (
          <div className="period-custom">
            <label className="field">From
              <input type="date" value={custom.from} max={custom.to} onChange={(e) => e.target.value && setCustom({ ...custom, from: e.target.value })} />
            </label>
            <label className="field">To
              <input type="date" value={custom.to} min={custom.from} max={utcDay()} onChange={(e) => e.target.value && setCustom({ ...custom, to: e.target.value })} />
            </label>
          </div>
        )}
        <p className="period-note">
          {formatDay(period.from)}{period.from !== period.to && ` to ${formatDay(period.to)}`}, days counted in UTC
        </p>
      </div>

      {state.status === "error" && <p className="notice notice-error" role="alert">{state.error}</p>}
      {state.status === "loading" && !data && <p className="loading-line">Loading the numbers…</p>}

      {data && (
        <div className={state.status === "loading" ? "stale" : undefined} aria-busy={state.status === "loading"}>
          {data.totals.questions === 0 ? (
            <div className="admin-empty" role="status">
              <strong>No question was asked in this period.</strong> Choose a longer period, or come back once
              learners have used the chat.
            </div>
          ) : (
            <>
              <Tiles data={data} />
              <PerDay rows={data.per_day} />
              <QuestionList
                title="Questions with no answer found"
                empty="Every question in this period found an answer."
                rows={data.unanswered}
                total={data.totals.no_answer}
              />
              <QuestionList
                title="Questions that failed"
                empty="No question ended in an error in this period."
                rows={data.failed}
                total={data.totals.error}
              />
              <BadResponses rows={data.bad_responses} total={data.ratings.bad} />
            </>
          )}
        </div>
      )}
      <p className="admin-req">Requirements: {page.requirement}</p>
    </section>
  );
}

function Tiles({ data }) {
  const t = data.totals;
  const lat = data.latency_ms;
  const rated = data.ratings.good + data.ratings.bad;
  return (
    <dl className="tiles">
      <div className="tile">
        <dt>Questions</dt>
        <dd className="tile-value num">{t.questions}</dd>
        <dd className="tile-sub">
          {t.answered} answered, {t.low_confidence} low confidence
        </dd>
      </div>
      <div className="tile">
        <dt>Failure rate</dt>
        <dd className="tile-value num">{percent(data.failure_rate)}</dd>
        <dd className="tile-sub">{t.error} ended in an error</dd>
      </div>
      <div className="tile">
        <dt>No answer found</dt>
        <dd className="tile-value num">{percent(data.no_answer_rate)}</dd>
        <dd className="tile-sub">{t.no_answer} question{t.no_answer === 1 ? "" : "s"}</dd>
      </div>
      <div className="tile">
        <dt>Median latency</dt>
        <dd className="tile-value num">{seconds(lat.p50)}</dd>
        <dd className="tile-sub">95% under {seconds(lat.p95)}, average {seconds(lat.average)}</dd>
      </div>
      <div className="tile">
        <dt>Ratings</dt>
        <dd className="tile-value num">{rated ? `${data.ratings.good} good` : "None"}</dd>
        <dd className="tile-sub">{rated ? `${data.ratings.bad} bad` : "No answer was rated"}</dd>
      </div>
    </dl>
  );
}

function PerDay({ rows }) {
  const [asTable, setAsTable] = useState(false);
  const [hover, setHover] = useState(null);
  const max = Math.max(1, ...rows.map((r) => r.questions));
  const step = niceStep(max);
  const top = Math.ceil(max / step) * step;
  const ticks = Array.from({ length: top / step + 1 }, (_, i) => i * step);
  const labelEvery = Math.ceil(rows.length / 8);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Questions per day</h2>
        <button type="button" className="btn-text" onClick={() => setAsTable(!asTable)}>
          {asTable ? "Show the chart" : "Show as a table"}
        </button>
      </div>
      {asTable ? (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Day</th><th className="num">Questions</th><th className="num">No answer</th><th className="num">Errors</th><th className="num">Median latency</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.day}>
                  <td>{formatDay(r.day)}</td><td className="num">{r.questions}</td><td className="num">{r.no_answer}</td>
                  <td className="num">{r.errors}</td><td className="num">{seconds(r.p50_ms)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="chart">
          <div className="chart-y" aria-hidden="true">
            {ticks.slice().reverse().map((v) => <span key={v} className="num">{v}</span>)}
          </div>
          <div className="chart-plot">
            {ticks.map((v) => <span key={v} className="chart-grid" style={{ bottom: `${(v / top) * 100}%` }} />)}
            <ol className="chart-bars" style={{ gridTemplateColumns: `repeat(${rows.length}, 1fr)` }}>
              {rows.map((r, i) => (
                <li
                  key={r.day}
                  className="chart-col"
                  tabIndex={0}
                  aria-label={`${formatDay(r.day)}: ${r.questions} questions, ${r.no_answer} with no answer, ${r.errors} errors`}
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(i)}
                  onBlur={() => setHover(null)}
                >
                  <span className="chart-bar" style={{ height: `${(r.questions / top) * 100}%` }} />
                  {hover === i && (
                    <span className={`chart-tip ${i > rows.length / 2 ? "chart-tip-left" : ""}`} role="tooltip">
                      <strong>{formatDay(r.day)}</strong>
                      <span className="num">{r.questions} questions</span>
                      <span className="num">{r.no_answer} no answer, {r.errors} errors</span>
                      <span className="num">median {seconds(r.p50_ms)}</span>
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </div>
          <ol className="chart-x" aria-hidden="true" style={{ gridTemplateColumns: `repeat(${rows.length}, 1fr)` }}>
            {rows.map((r, i) => <li key={r.day}>{i % labelEvery === 0 ? shortDay(r.day) : ""}</li>)}
          </ol>
        </div>
      )}
    </section>
  );
}

function QuestionList({ title, empty, rows, total }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        <span className="muted num">{total}</span>
      </div>
      {rows.length === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <ul className="qlist">
          {rows.map((q) => (
            <li key={q.id}>
              <details>
                <summary>
                  <span className="q-text">{q.query}</span>
                  <span className="q-time">{formatTime(q.asked_at)}</span>
                </summary>
                <dl className="q-detail">
                  {q.rewritten_query && <><dt>Searched as</dt><dd>{q.rewritten_query}</dd></>}
                  <dt>Page</dt><dd>{q.endpoint === "chat" ? "Chat" : `/${q.endpoint}`}</dd>
                  <dt>Best match score</dt><dd className="num">{q.top_score ?? "nothing returned"}</dd>
                  <dt>Figures returned</dt><dd className="num">{q.result_count}</dd>
                  <dt>Answer</dt><dd>{answerMode(q.answer_mode)}</dd>
                  <dt>Time taken</dt><dd className="num">{seconds(q.latency_ms)}</dd>
                  {q.error && <><dt>Error</dt><dd><code>{q.error}</code></dd></>}
                </dl>
              </details>
            </li>
          ))}
        </ul>
      )}
      {total > rows.length && <p className="muted">Only the most recent {rows.length} of {total} are listed.</p>}
    </section>
  );
}

function BadResponses({ rows, total }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Answers rated bad</h2>
        <span className="muted num">{total}</span>
      </div>
      {rows.length === 0 ? (
        <p className="muted">No answer of this period was rated bad.</p>
      ) : (
        <ul className="qlist">
          {rows.map((r) => (
            <li key={`${r.query_id}-${r.rated_by}`} className="q-row">
              <span className="q-text">{r.query}</span>
              <span className="q-meta">
                {r.rewritten_query && <>searched as “{r.rewritten_query}”, </>}
                {answerMode(r.answer_mode).toLowerCase()}, rated by {r.rated_by} on {formatTime(r.rated_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function answerMode(mode) {
  return { llm: "Written answer", extractive: "Quoted passages (no summary)", no_answer: "No answer" }[mode] || "Figures only";
}
function percent(rate) {
  if (rate === null || rate === undefined) return "–";
  const p = rate * 100;
  return `${p < 10 && p > 0 ? p.toFixed(1) : Math.round(p)}%`;
}
function seconds(ms) {
  if (ms === null || ms === undefined) return "–";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}
function niceStep(max) {
  const raw = max / 4;
  const pow = 10 ** Math.floor(Math.log10(raw || 1));
  return Math.max(1, [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw) || 1);
}
function formatDay(day) {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { timeZone: "UTC", weekday: "short", month: "short", day: "numeric" });
}
function shortDay(day) {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { timeZone: "UTC", month: "short", day: "numeric" });
}
function formatTime(value) {
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
