# CLAUDE.md - P7 Technical Training Assistant

Final-year project (ESIB-USJ, supervisor Mr. Georges Salloum). A learner asks a technical question and gets the right passage AND the actual figure from FAA handbooks, with handbook name and printed page number. Authorities: the brief (ESIB-P7-technical-training-assistant.pdf) and our SRS/SPEC (docs/SPEC.md). Never remove or change anything the brief or SRS requires.

## Project rules
- The GitHub repository is PUBLIC. Never read, print, log or commit the values in .env. Check only that a setting name exists. No PDFs, no data/ folder, no keys in Git.
- Keep CRLF line endings in files you create or edit (Windows). Edit CSV files as text; never open or convert them with Excel (it turns figure numbers such as "1-20" into dates).
- Never claim a command, test, download or deployment succeeded unless you saw its output.
- evaluation/runs/<name>/ folders are evidence: never overwrite or edit them.

## Project map
- ingestion/   download_handbook.py, extract_figures.py, chunk_text.py, load_db.py, migrate.py, make_thumbnails.py, render_pages.py
- backend/     app.py (FastAPI: /search, /answer, figure images), retrieval.py (retrieve(), thresholds), answer.py (LLM answer, citations, numeric guard BR-004), query_log.py, prompts/answer_system_v*.txt
- evaluation/  questions.csv (50 questions), run_eval.py, prompt_eval.py, check_questions_in_db.py, judgements.csv, runs/<name>/
- db/migrations/  numbered SQL files (no Alembic)
- frontend/    React (Vite); FastAPI serves frontend/dist
- docs/        SPEC.md, EVALUATION.md, AI_LOG.md
- Database: PostgreSQL + pgvector in Docker, host port 5433, always 127.0.0.1. Embeddings: BAAI/bge-small-en-v1.5 (384 dims). LLM settings only in .env: LLM_PROVIDER, LLM_BASE_URL, LLM_MODEL, LLM_API_KEY.

## Commands (PowerShell, repository root, .venv active)
- .\.venv\Scripts\Activate.ps1
- python -m pytest -q          (about 3 minutes; 220+ tests)
- python evaluation/run_eval.py run <run_name>
- python evaluation/prompt_eval.py <run_name> --prompt v2
