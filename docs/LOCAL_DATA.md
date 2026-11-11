# Local test data (database + extracted figures)

The database content and the extracted figures are too large for Git (`data/` and `dumps/` are ignored).
To test the API and the web interface against the real data, restore them from the two files shared privately (Google Drive link, not public).

| File | Content | Size |
| --- | --- | --- |
| `p7_db_2026-11-11.dump` | PostgreSQL custom-format dump of the `p7` database: documents, pages, chunks, figures, figure_refs, embeddings, schema_migrations. `query_log` is included as an empty table (its rows are excluded: they are real test questions). | ~10 MB |
| `data_extracted_2026-11-11.zip` | `data/extracted/` for FAA-H-8083-15B and FAA-H-8083-25C: figure images, page images, `figures.jsonl`, `chunks.jsonl`. The API serves figure images from here. | ~336 MB |

The dump was made from the code on `feature/P7-33-query-reformulation` (migrations 001 to 006). Migration 006 (`figure_image_embeddings`) is not on `main` yet; on `main` that table is simply unused.

## Steps (Windows PowerShell, repository root)

1. Download both files from the shared link and put them in a folder `dumps\` at the repository root.
2. If you have no `.env` yet: `Copy-Item .env.example .env`, then set your own `POSTGRES_PASSWORD`.
3. Start the database and wait until it is `healthy`:
   ```
   docker compose up -d
   docker compose ps
   ```
4. Restore the dump (replaces existing tables of the same name):
   ```
   docker cp dumps\p7_db_2026-11-11.dump p7-db:/tmp/p7.dump
   docker exec p7-db sh -c 'pg_restore --clean --if-exists --no-owner -U $POSTGRES_USER -d $POSTGRES_DB /tmp/p7.dump'
   ```
   A few "does not exist, skipping" notices on a fresh database are normal.
5. Check:
   ```
   docker exec p7-db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -c "select handbook_id, count(*) from figures group by 1;"'
   ```
   Expected: FAA-H-8083-15B 347, FAA-H-8083-25C 502.
6. Unzip the figures (the archive already contains the `extracted\` folder):
   ```
   Expand-Archive dumps\data_extracted_2026-11-11.zip -DestinationPath data -Force
   ```
   Check: `data\extracted\FAA-H-8083-15B\figures\1-1.png` exists.
7. Start the backend (venv active): `python -m uvicorn backend.app:app --port 8000`
8. Test: open http://127.0.0.1:8000/search?q=airspace%20classes . The first result should be Figure 1-1 of FAA-H-8083-15B. If `/search` requires login on your branch, send the token.
9. Frontend: `cd frontend; npm run dev`, open http://localhost:5173 .

Do not commit anything from `dumps\` or `data\`.
