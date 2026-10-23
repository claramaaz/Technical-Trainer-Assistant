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
Week 1 of 12. Currently: specification phase (no application code yet).

## Links
- Deployed application: *not deployed yet*
- Task board (Jira): *to be created*

## Documents
- [SPEC.md](SPEC.md): software requirements specification
- [AI_LOG.md](AI_LOG.md): record of AI-assisted work, including mistakes and how we caught them
- EVALUATION.md: evaluation set and measured results *(coming)*

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
*To be written in Week 1, once the project structure exists.*

## Git workflow
- `main` is protected; work happens on branches named `feature/P7-<ticket>-<short-name>`
- Every change goes through a pull request reviewed by the other teammate
- Commit messages start with the Jira ticket: `P7-14: detect figure captions`
- Tags mark the specification (`spec-v1`) and each gate

## Safety note
This is a training tool. Answers are not operational aviation guidance.