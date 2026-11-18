import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import AssistantTurn, { NO_ANSWER } from "./AssistantTurn.jsx";
import SourceDialog from "./SourceDialog.jsx";
import "./chat.css";

const MAX_LENGTH = 500;         // same limit as the server (POST /chat)
const HISTORY_TURNS = 3;        // the server keeps the last 3 questions and answers (chat.py)
const EXAMPLES = [
  "What are the four forces acting on an airplane in flight?",
  "How does the pitot-static system work?",
  "What causes carburetor icing?",
];

// The learner page (P7-56; FR-009, UC-02): a cumulative chat, like the middle column of NotebookLM.
// Every message is sent with the conversation so far, so a follow-up such as "and if it is blocked?"
// is understood (the server rewrites it into a standalone question before searching).
export default function ChatPage({ onSessionExpired }) {
  const [turns, setTurns] = useState([]); // { id, message, status: loading | done | error, data?, error? }
  const [draft, setDraft] = useState("");
  const [empty, setEmpty] = useState(false);
  const [source, setSource] = useState(null); // { result, query } shown in the View source window
  const busy = turns.some((t) => t.status === "loading");
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const nextId = useRef(1);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, turns[turns.length - 1]?.status]);

  // The conversation sent to the server: the learner's questions and the answers as plain text.
  function historyBefore(list) {
    return list
      .filter((t) => t.status === "done")
      .slice(-HISTORY_TURNS)
      .flatMap((t) => [
        { role: "user", content: t.message },
        { role: "assistant", content: answerText(t.data) },
      ]);
  }

  async function ask(text) {
    const message = text.trim();
    if (!message) return setEmpty(true); // UC-02 A2
    if (busy) return;
    setEmpty(false);
    const id = nextId.current++;
    const earlier = turns;
    setTurns([...earlier, { id, message, status: "loading" }]);
    setDraft("");
    try {
      const data = await api("/chat", {
        method: "POST",
        json: { message, history: historyBefore(earlier), k: 5 },
        onSessionExpired,
      });
      setTurns((list) => list.map((t) => (t.id === id ? { ...t, status: "done", data } : t)));
    } catch (error) {
      if (error.status === 401) return;
      setTurns((list) => list.map((t) => (t.id === id ? { ...t, status: "error", error: error.message } : t)));
    }
    inputRef.current?.focus({ preventScroll: true });
  }

  function onKeyDown(event) {
    // Enter sends, Shift+Enter makes a new line (as in most chats).
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      ask(draft);
    }
  }

  return (
    <div className="chat">
      <div className="chat-scroll">
        {turns.length === 0 ? (
          <section className="chat-welcome">
            <h1>What would you like to understand?</h1>
            <p>
              Ask about a topic or a symptom. You get an explanation from the FAA handbooks with the figure
              and the page it comes from.
            </p>
            <ul className="examples">
              {EXAMPLES.map((q) => (
                <li key={q}>
                  <button type="button" className="follow-up" onClick={() => ask(q)}>
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : (
          <ol className="turns" aria-live="polite">
            {turns.map((t) => (
              <li key={t.id} className="turn">
                <p className="turn-user">{t.message}</p>
                <AssistantTurn
                  turn={t}
                  busy={busy}
                  onAsk={ask}
                  onRetry={() => ask(t.message)}
                  onOpenSource={(result) => setSource({ result, query: t.message })}
                  onSessionExpired={onSessionExpired}
                />
              </li>
            ))}
          </ol>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          ask(draft);
        }}
      >
        {empty && <p className="composer-hint" role="alert">Please type a question.</p>}
        <div className="composer-box">
          <label htmlFor="chat-input" className="visually-hidden">Your question</label>
          <textarea
            id="chat-input"
            ref={inputRef}
            rows={1}
            maxLength={MAX_LENGTH}
            value={draft}
            placeholder={turns.length ? "Ask a follow-up question" : "Ask a question about the handbooks"}
            onChange={(e) => {
              setDraft(e.target.value);
              if (empty) setEmpty(false);
            }}
            onKeyDown={onKeyDown}
            enterKeyHint="send"
          />
          <button type="submit" className="send" disabled={busy} aria-label="Send">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
        <p className="composer-foot">Training use only. Answers are not operational aviation guidance.</p>
      </form>

      <SourceDialog
        result={source?.result}
        query={source?.query}
        onClose={() => setSource(null)}
        onSessionExpired={onSessionExpired}
      />
    </div>
  );
}

function answerText(data) {
  if (!data || data.answer?.mode === "no_answer" || !data.results?.length) return NO_ANSWER;
  return (data.answer?.sentences || []).map((s) => s.text).join(" ");
}
