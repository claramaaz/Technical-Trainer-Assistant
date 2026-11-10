# Prompt evaluation `2026-11-10-prompt-v2` (prompt v2)

- Date (UTC): 2026-11-10 17:32; git commit: ec7fa3a
- Rows (question x run): 150; modes: {'llm': 103, 'extractive': 23, 'no_answer': 24}
- **Rows with mode llm: 103.** The first measures below use only these rows.

| Measure | Result |
| --- | --- |
| Sentences returned by the LLM (llm rows) | 202 |
| Sentences kept (cited, valid id, numbers ok) | 201/202 = 99.5% |
| Dropped by the numeric guard | 1 |
| Dropped for a missing or unknown citation | 0 |
| Stability (same cited ids in every llm run), questions with 2+ llm runs | 24/35 = 68.6% |
| Correct refusals on no-answer questions (mode no_answer, per run) | 18/24 = 75.0% |
| No-answer runs where the LLM itself returned no sentence | 6 |

Fallbacks (reported separately; they are not LLM answers):

| Measure | Result |
| --- | --- |
| Extractive fallbacks (rows) | 23 (no_valid_sentences: 23) |
| http_error rows by last HTTP status | none |
| LLM calls that needed a retry | 32 (38 retries in all; 32 of these calls ended without http_error) |
| LLM answered but nothing survived the checks (no_valid_sentences) | 23 rows, 0 sentences, all dropped; not in the share above |

Reading notes:
- http_error / timeout / missing_api_key are server or setup problems, not the prompt. A run with many of them says little about the prompt.
- Questions with fewer than 2 llm runs cannot be compared and are left out of stability: none
- Unstable questions: Q004, Q009, Q012, Q014, Q016, Q023, Q029, Q030, Q040, Q041, Q042
