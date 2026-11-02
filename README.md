# Technical Training Assistant (Project P7)

ESIB – Université Saint-Joseph, Computer Engineering. End-of-semester project P7.

A web application that answers technical questions about aviation training
manuals with the matching explanation text **and the correct diagram**, together
with the handbook name and page number so the reader can check the original.
It is built to work on a phone with a slow connection.

## Team
- Clara Maaz
- Mia Badran
- Supervisor: Mr. Georges Salloum

## Status
Week 0 of 12. Specification tagged (`spec-v1`). Working on the Week 1 gate: one handbook ingested with figure and caption counts.

## Links
- Deployed application: *not deployed yet*
- Task board (Jira): *to be created*

## Documents
- [docs/SPEC.md](docs/SPEC.md): software requirements specification
- [docs/AI_LOG.md](docs/AI_LOG.md): record of AI-assisted work, including mistakes and how we caught them
- [docs/EVALUATION.md](docs/EVALUATION.md): evaluation set, method and measured results

## Corpus
FAA aviation handbooks and manuals (United States Government works, public domain):
https://www.faa.gov/regulations_policies/handbooks_manuals/aviation

The PDF files are large (up to 205 MB), so they are **not stored in this repository**.
The licence, source URL and retrieval date of every document are recorded in the database
when it is ingested.

## Planned technologies (as directed by the supervisor)
Python, PostgreSQL with pgvector, an API connecting the backend to a web interface, Jira.
Other choices (API framework, embedding model, hosting) are documented in SPEC.md
once confirmed.

## How to run
Requires Python 3.11+. Run from the repository root (Windows PowerShell shown).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python ingestion\download_handbook.py FAA-H-8083-15B      # download + verify into data\raw\
python ingestion\inspect_pdf.py data\raw\FAA-H-8083-15B.pdf
python ingestion\extract_figures.py data\raw\FAA-H-8083-15B.pdf
python ingestion\sample_check.py draw FAA-H-8083-15B --n 20 --seed 7
python -m pytest -q                                          # tests
```

Downloaded PDFs and extracted figures go to `data/`, which is not committed.

## Database (PostgreSQL + pgvector, in Docker)
The database runs in a Docker container (image `pgvector/pgvector:0.8.7-pg17`); it is
not installed on Windows. Requires Docker Desktop to be running.

```powershell
Copy-Item .env.example .env          # then edit .env and choose your own POSTGRES_PASSWORD
docker compose up -d                 # starts the database; wait until it is "healthy"
docker compose ps
"CREATE EXTENSION IF NOT EXISTS vector;" | docker compose exec -T db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB'
```

- `.env` holds the credentials and is never committed; `.env.example` is the committed template.
- The database listens on `127.0.0.1:5433` (this computer only). Port 5433 and not 5432 avoids a clash with a
  PostgreSQL that may already be installed on Windows. Change `POSTGRES_PORT` in `.env` if 5433 is taken.
- Use `127.0.0.1`, not `localhost`: `localhost` tries IPv6 first and each connection then waits about 10 seconds.
- Connect from Python with `postgresql://<POSTGRES_USER>:<POSTGRES_PASSWORD>@127.0.0.1:5433/<POSTGRES_DB>`.
- Data lives in the Docker volume `p7_pgdata` and survives `docker compose down`.
  `docker compose down -v` deletes the volume and all data.
- Create or update the tables (safe to run again): `python ingestion\migrate.py`. It applies the numbered files in `db\migrations\` and records them in `schema_migrations`.
- Load an extracted handbook (after `migrate.py`): `python ingestion\load_db.py FAA-H-8083-15B`. It can be run again; `--reset` deletes that handbook's rows and loads from scratch. A handbook whose licence is empty or "unknown" in `corpus\handbooks.csv` is loaded but not searchable.
- Stop: `docker compose down`.

## Git workflow
- `main` is protected; work happens on branches named `feature/P7-<ticket>-<short-name>`
- Every change goes through a pull request reviewed by the other teammate
- Commit messages start with the Jira ticket: `P7-14: detect figure captions`
- Tags mark the specification (`spec-v1`) and each gate

## Safety note
This is a training tool. Answers are not operational aviation guidance.