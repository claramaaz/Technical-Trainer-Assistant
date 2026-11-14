# Prompt evaluation `2026-11-12-refusal` (prompt v2)

- Date (UTC): 2026-11-12 14:12; git commit: acb8c4d
- Rows (question x run): 50; modes: {'llm': 34, 'extractive': 4, 'no_answer': 12}
- **Rows with mode llm: 34.** The first measures below use only these rows.

| Measure | Result |
| --- | --- |
| Sentences returned by the LLM (llm rows) | 63 |
| Sentences kept (cited, valid id, numbers ok) | 62/63 = 98.4% |
| Dropped by the numeric guard | 1 |
| Dropped for a missing or unknown citation | 0 |
| Stability (same cited ids in every llm run), questions with 2+ llm runs | 0/0 (n/a) |
| Correct refusals on no-answer questions (mode no_answer, per run) | 8/8 = 100.0% |
| No-answer runs where the LLM itself returned no sentence | 0 |
| Answerable questions turned into no answer by the LLM refusal (low confidence) | Q031, Q032 |

Fallbacks (reported separately; they are not LLM answers):

| Measure | Result |
| --- | --- |
| Extractive fallbacks (rows) | 4 (no_valid_sentences: 4) |
| http_error rows by last HTTP status | none |
| LLM calls that needed a retry | 17 (19 retries in all; 17 of these calls ended without http_error) |
| LLM answered but nothing survived the checks (no_valid_sentences) | 4 rows, 0 sentences, all dropped; not in the share above |

Reading notes:
- http_error / timeout / missing_api_key are server or setup problems, not the prompt. A run with many of them says little about the prompt.
- Questions with fewer than 2 llm runs cannot be compared and are left out of stability: Q001, Q002, Q003, Q004, Q005, Q007, Q008, Q009, Q010, Q012, Q013, Q014, Q015, Q016, Q017, Q019, Q021, Q022, Q023, Q027, Q028, Q029, Q030, Q033, Q034, Q035, Q037, Q038, Q039, Q040, Q041, Q042, Q043, Q044
- Unstable questions: none
