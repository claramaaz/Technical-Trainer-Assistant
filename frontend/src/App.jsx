import { useRef, useState } from "react";
import ResultCard from "./ResultCard.jsx";

const NO_ANSWER = "No adequate answer found in the handbook";

export default function App() {
  const [query, setQuery] = useState("");
  // status: idle | empty | loading | error | no-answer | results
  const [status, setStatus] = useState("idle");
  const [results, setResults] = useState([]);
  const [errorText, setErrorText] = useState("");
  const latest = useRef(null); // lets a new search cancel the previous one

  async function onSubmit(event) {
    event.preventDefault();
    const q = query.trim();
    if (!q) {
      latest.current?.abort();
      setResults([]);
      setStatus("empty");
      return;
    }
    latest.current?.abort();
    const controller = new AbortController();
    latest.current = controller;
    setResults([]);
    setStatus("loading");
    try {
      const response = await fetch(`/search?q=${encodeURIComponent(q)}&k=5`, {
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`The server answered with an error (${response.status}).`);
      const data = await response.json();
      if (data.reason === "no_adequate_answer" || !data.results?.length) {
        setStatus("no-answer");
      } else {
        setResults(data.results);
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
      <h1>Ask the handbook</h1>
      <form onSubmit={onSubmit} className="search">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. What are the parts of the inner ear?"
          aria-label="Question"
        />
        <button type="submit" disabled={status === "loading"}>
          Search
        </button>
      </form>

      {status === "empty" && <p className="hint" role="alert">Please type a question.</p>}
      {status === "loading" && <p className="hint" role="status">Searching…</p>}
      {status === "error" && <p className="error" role="alert">{errorText}</p>}
      {status === "no-answer" && <p className="no-answer" role="alert">{NO_ANSWER}</p>}
      {status === "results" &&
        results.map((r) => <ResultCard key={r.id} result={r} />)}
    </main>
  );
}
