import { useRef, useState } from "react";
import ResultCard from "./ResultCard.jsx";

const NO_ANSWER = "No adequate answer found in the handbook";
// FR-002 / brief section 12: a weak match is shown, but never presented as a sure one.
const LOW_CONFIDENCE =
  "This answer may not match your question well. Check the source before relying on it.";

export default function App({ onSessionExpired }) {
  const [query, setQuery] = useState("");
  // status: idle | empty | loading | error | no-answer | results
  const [status, setStatus] = useState("idle");
  const [results, setResults] = useState([]);
  const [confidence, setConfidence] = useState(null); // "high" | "low" | null (P7-48)
  const [errorText, setErrorText] = useState("");
  const latest = useRef(null); // lets a new search cancel the previous one

  async function onSubmit(event) {
    event.preventDefault();
    const q = query.trim();
    if (!q) {
      latest.current?.abort();
      setResults([]);
      setConfidence(null);
      setStatus("empty");
      return;
    }
    latest.current?.abort();
    const controller = new AbortController();
    latest.current = controller;
    setResults([]);
    setConfidence(null);
    setStatus("loading");
    try {
      const response = await fetch(`/search?q=${encodeURIComponent(q)}&k=5`, {
        signal: controller.signal,
      });
      if (response.status === 401) {
        onSessionExpired?.(); // token expired or logged out elsewhere (P7-35)
        return;
      }
      if (!response.ok) throw new Error(`The server answered with an error (${response.status}).`);
      const data = await response.json();
      if (data.reason === "no_adequate_answer" || !data.results?.length) {
        setStatus("no-answer");
      } else {
        setResults(data.results);
        // "confidence" is only sent when figures are returned; anything but "low" counts as high.
        setConfidence(data.confidence === "low" ? "low" : "high");
        setStatus("results");
      }
    } catch (error) {
      if (error.name === "AbortError") return; // replaced by a newer search
      setErrorText(
        error instanceof TypeError
          ? "Could not reach the server. Check your connection and try again."
          : error.message
      );
      setStatus("error");
    }
  }

  return (
    <main className="page">
      <header className="top">
        <h1>Ask the handbook</h1>
        <p className="subtitle">FAA handbook explanations with the matching diagram and its page.</p>
      </header>

      <form onSubmit={onSubmit} className="search" role="search">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. What are the parts of the inner ear?"
          aria-label="Question"
          enterKeyHint="search"
        />
        <button type="submit" disabled={status === "loading"}>
          {status === "loading" ? "Searching…" : "Search"}
        </button>
      </form>

      {status === "empty" && <p className="hint" role="alert">Please type a question.</p>}
      {status === "loading" && <p className="hint" role="status">Searching the handbooks…</p>}
      {status === "error" && <p className="error" role="alert">{errorText}</p>}
      {status === "no-answer" && <p className="no-answer" role="alert">{NO_ANSWER}</p>}

      {status === "results" && confidence === "low" && (
        <div className="low-confidence" role="alert">
          <strong>Low confidence.</strong> {LOW_CONFIDENCE}
        </div>
      )}
      {status === "results" &&
        results.map((r) => <ResultCard key={r.id} result={r} />)}

      <footer className="safety">Training tool only. Not operational aviation guidance.</footer>
    </main>
  );
}
