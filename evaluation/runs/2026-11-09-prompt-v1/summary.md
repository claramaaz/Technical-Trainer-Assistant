# Prompt evaluation `2026-11-09-prompt-v1` (prompt v1)

- Date (UTC): 2026-11-09 07:21; git commit: ec7fa3a
- Rows (question x run): 150; modes: {'extractive': 83, 'llm': 43, 'no_answer': 24}

| Measure | Result |
| --- | --- |
| Sentences returned by the LLM | 71 |
| Sentences kept (cited, valid id, numbers ok) | 70/71 = 98.6% |
| Dropped by the numeric guard | 1 |
| Dropped for a missing or unknown citation | 0 |
| Correct refusals on no-answer questions (mode no_answer, per run) | 18/24 = 75.0% |
| No-answer runs where the LLM itself returned no sentence | 4 |
| Stability (same cited ids in every run) | 16/42 = 38.1% |
| Extractive fallbacks (rows) | 83 (http_error: 67, no_valid_sentences: 16) |

Reading notes:
- Extractive fallbacks with reason http_error / timeout / missing_api_key are LLM or Groq problems; no_valid_sentences means the LLM answered but nothing survived the checks.
- Stability counts questions that were sent to the LLM; questions refused by retrieval are left out.
- Unstable questions: Q002, Q004, Q005, Q008, Q009, Q010, Q012, Q013, Q014, Q015, Q017, Q021, Q022, Q023, Q028, Q029, Q030, Q032, Q033, Q034, Q035, Q038, Q040, Q041, Q042, Q044
