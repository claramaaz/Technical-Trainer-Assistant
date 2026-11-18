import { useRef, useState } from "react";
import AnswerText from "./AnswerText.jsx";
import OtherFigures from "./OtherFigures.jsx";
import ResultCard from "./ResultCard.jsx";
import "./answer.css";

const NO_ANSWER = "No adequate answer found in the handbook";
// FR-002 / brief section 12: a weak match is shown, but never presented as a sure one.
const LOW_CONFIDENCE =
  "This answer may not match your question well. Check the source before relying on it.";

// The search page (UC-02). It calls GET /answer, which returns
//   { answer: { mode, sentences: [{ text, citations }] }, results, confidence }
// and shows: the written answer, then ONE figure large (the brief asks for "the diagram"),
// then the other returned figures folded away under "Other possible figures (n)".
// answer.mode "no_answer" shows only the no-answer message, with no figure (FR-002).
export default function App({ onSessionExpired }) {
  const [query, setQuery] = useState("");
  // status: idle | empty | loading | error | no-answer | results
  const [status, setStatus] = useState("idle");
  const [answer, setAnswer] = useState(null);
  const [results, setResults] = useState([]);
  const [confidence, setConfidence] = useState(null); // "high" | "low" | null (P7-48)
  // The question the shown results answer (not the text being typed): a "Wrong figure"
  // report is stored with it (P7-38, UC-03).
  const [searchedQuery, setSearchedQuery] = useState("");
  const [othersOpen, setOthersOpen] = useState(false);
  const [errorText, setErrorText] = useState("");
  const latest = useRef(null); // lets a new search cancel the previous one

  function clear() {
    setAnswer(null);
    setResults([]);
    setConfidence(null);
    setOthersOpen(false);
  }

  async function onSubmit(event) {
    event.preventDefault();
    const q = query.trim();
    latest.current?.abort();
    clear();
    if (!q) {
      setStatus("empty");
      return;
    }
    const controller = new AbortController();
    latest.current = controller;
    setStatus("loading");
    try {
      const response = await fetch(`/answer?q=${encodeURIComponent(q)}&k=5`, {
        signal: controller.signal,
      });
      if (response.status === 401) {
        onSessionExpired?.(); // token expired or logged out elsewhere (P7-35)
        return;
      }
      if (!response.ok) throw new Error(`The server answered with an error (${response.status}).`);
      const data = await response.json();
      if (data.answer?.mode === "no_answer" || !data.results?.length) {
        setStatus("no-answer"); // no figure is shown with a no-answer (FR-002)
        return;
      }
      setAnswer(data.answer);
      setResults(data.results);
      setSearchedQuery(q);
      // "confidence" is only sent when figures are returned; anything but "low" counts as high.
      setConfidence(data.confidence === "low" ? "low" : "high");
      setStatus("results");
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

  // A citation in the answer was clicked: bring that figure into view (and open
  // "Other possible figures" first if it is one of them).
  function showFigure(id) {
    if (results[0]?.id !== id) setOthersOpen(true);
    // After React has drawn the opened list.
    requestAnimationFrame(() => {
      const el = document.getElementById(`fig-${id}`);
      if (!el) return;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("highlight");
      setTimeout(() => el.classList.remove("highlight"), 1500);
    });
  }

  const [main, ...others] = results;

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
      {status === "loading" && (
        <p className="hint" role="status">Searching the handbooks and writing the answer…</p>
      )}
      {status === "error" && <p className="error" role="alert">{errorText}</p>}
      {status === "no-answer" && <p className="no-answer" role="alert">{NO_ANSWER}</p>}

      {status === "results" && (
        <>
          {confidence === "low" && (
            <div className="low-confidence" role="alert">
              <strong>Low confidence.</strong> {LOW_CONFIDENCE}
            </div>
          )}
          {answer?.sentences?.length > 0 && (
            <AnswerText answer={answer} results={results} onShowFigure={showFigure} />
          )}
          {/* The key includes the question, so a figure returned again for a new question
              starts with a fresh "Wrong figure" button. */}
          <ResultCard
            key={`${searchedQuery}|${main.id}`}
            result={main}
            query={searchedQuery}
            onSessionExpired={onSessionExpired}
          />
          <OtherFigures
            key={searchedQuery}
            results={others}
            open={othersOpen}
            onToggle={() => setOthersOpen(!othersOpen)}
            query={searchedQuery}
            onSessionExpired={onSessionExpired}
          />
        </>
      )}

      <footer className="safety">Training tool only. Not operational aviation guidance.</footer>
    </main>
  );
}
