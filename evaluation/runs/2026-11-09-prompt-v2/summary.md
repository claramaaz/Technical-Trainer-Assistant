# Prompt evaluation `2026-11-09-prompt-v2` (prompt v2)

- Date (UTC): 2026-11-09 16:43; git commit: ec7fa3a
- Rows (question x run): 150; modes: {'llm': 52, 'extractive': 74, 'no_answer': 24}
- **Rows with mode llm: 52.** The first measures below use only these rows.

| Measure | Result |
| --- | --- |
| Sentences returned by the LLM (llm rows) | 91 |
| Sentences kept (cited, valid id, numbers ok) | 89/91 = 97.8% |
| Dropped by the numeric guard | 2 |
| Dropped for a missing or unknown citation | 0 |
| Stability (same cited ids in every llm run), questions with 2+ llm runs | 12/16 = 75.0% |
| Correct refusals on no-answer questions (mode no_answer, per run) | 18/24 = 75.0% |
| No-answer runs where the LLM itself returned no sentence | 0 |

Fallbacks (reported separately; they are not LLM answers):

| Measure | Result |
| --- | --- |
| Extractive fallbacks (rows) | 74 (http_error: 66, no_valid_sentences: 8) |
| http_error rows by last HTTP status | 429: 17, none: 49 |
| LLM calls that needed a retry | 38 (86 retries in all; 21 of these calls ended without http_error) |
| LLM answered but nothing survived the checks (no_valid_sentences) | 8 rows, 0 sentences, all dropped; not in the share above |

Reading notes:
- http_error / timeout / missing_api_key are server or setup problems, not the prompt. A run with many of them says little about the prompt.
- Questions with fewer than 2 llm runs cannot be compared and are left out of stability: Q016, Q021, Q022, Q027, Q028, Q029, Q030
- Unstable questions: Q002, Q004, Q009, Q012
