"""Chat evaluation helpers (P7-55): no LLM, no database."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))
import chat_eval  # noqa: E402

R = [{"handbook_id": "A", "figure_id": "1-1", "score": 0.7, "cited": True},
     {"handbook_id": "A", "figure_id": "2-2", "score": 0.8, "cited": False}]


def turn(results, mode="llm", question="q", sentences=("One. [1]",)):
    return {"question": question, "results": results, "follow_ups": ["a", "b", "c"], "rewrite_fallback": None,
            "answer": {"mode": mode, "fallback_reason": None, "sentences": [{"text": s} for s in sentences]}}


def test_rank_in_shown_order_and_in_score_order():
    q = {"id": "Q1", "type": "topic", "handbook": "A", "figure_number": "1-1"}
    row = chat_eval.single_row(q, turn(R), 12)
    assert (row["rank_shown"], row["rank_by_score"], row["first_shown"]) == (1, 2, "A 1-1")


def test_missing_figure_has_no_rank():
    assert chat_eval.rank_of(R, "B", "1-1") is None


def test_history_after_one_turn_has_the_question_and_the_answer_text():
    assert chat_eval.history_of("what is X", turn(R, sentences=("A. [1]", "B. [2]"))) == [
        {"role": "user", "content": "what is X"}, {"role": "assistant", "content": "A. [1] B. [2]"}]
    assert chat_eval.history_of("q", turn([], mode="no_answer", sentences=())) == [{"role": "user", "content": "q"}]


def test_run_asks_every_question_and_writes_the_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_eval, "RUNS", tmp_path)
    monkeypatch.setattr(chat_eval.subprocess, "run", lambda *a, **k: type("P", (), {"stdout": "abc123"})())
    asked = []

    def fake_chat(message, history, k):
        asked.append((message, len(history)))
        return turn(R, question="standalone " + message)
    single, follow = chat_eval.run("t", chat=fake_chat, retrieve=lambda q, k: {"results": R[1:]},
                                   pause=0, sleep=lambda s: None)
    assert len(single) == 50 and len(follow) == 10
    assert asked[50:52] == [("What is a turn coordinator?", 0), ("What is the purpose of its rate gyro?", 2)]
    summary = (tmp_path / "t" / "summary.md").read_text(encoding="utf-8")
    assert "| with history (chat, rewritten) |" in summary and "No-answer questions" in summary


def test_a_failed_question_is_recorded_and_the_run_goes_on(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_eval, "RUNS", tmp_path)
    monkeypatch.setattr(chat_eval.subprocess, "run", lambda *a, **k: type("P", (), {"stdout": "abc"})())
    calls = []

    def flaky(message, history, k):
        calls.append(message)
        if len(calls) == 2:
            raise RuntimeError("HTTP 429")
        return turn(R)
    single, _follow = chat_eval.run("t", chat=flaky, pause=0, sleep=lambda s: None, parts="A")
    assert len(single) == 50 and single[1]["mode"] == "error" and "429" in single[1]["fallback_reason"]
    assert (tmp_path / "t" / "chat_single.csv").exists() and not (tmp_path / "t" / "chat_followups.csv").exists()

