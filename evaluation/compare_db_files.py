"""Check that searching in PostgreSQL gives the same answer as the old file-based search (P7-22).

Usage (repository root, database running and loaded):
    python evaluation/compare_db_files.py

For every question in evaluation/questions.csv it takes the top 5 figures and their scores
  - from the files (figures.jsonl + the .npy embeddings, dot product: how retrieve() worked
    before the database), and
  - from the database (backend.retrieval.rank, cosine distance in pgvector),
and compares them. Then it prints Hit@1, Hit@5 and MRR@5 from the database ranking over the
answerable questions, the same rule as docs/EVALUATION.md section 3.2.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from backend import retrieval  # noqa: E402
from baseline_retrieval import QUERY_PREFIX, load_questions  # noqa: E402
from figure_retrieval import load_jsonl, paths  # noqa: E402

HANDBOOK = "FAA-H-8083-15B"
TOLERANCE = 1e-6


def file_ranking(vectors, figures, query_vector, k):
    """[(figure_number, score)] best first, as the old rank() did it."""
    scores = vectors @ query_vector
    return [(figures[i]["figure_number"], float(scores[i])) for i in np.argsort(-scores)[:k]]


def db_ranking(index, query_vector, k):
    # only the handbook of the questions: the file reference below holds that handbook alone
    return [(index.documents[i]["figure_number"], s)
            for i, s in retrieval.rank(index, query_vector, k, handbooks=[HANDBOOK])]


def compare(k=5):
    """One dict per question: id, expected figure, both top-k lists, whether they agree."""
    figures = load_jsonl(ROOT / "data" / "extracted" / HANDBOOK / "figures.jsonl", "run extract_figures.py")
    vectors = np.load(ROOT / paths(HANDBOOK, retrieval.MODEL_NAME)[2])
    index = retrieval.load_index()
    questions = load_questions(HANDBOOK)
    qvecs = retrieval._model().encode([QUERY_PREFIX + q["question"] for q in questions],
                                      normalize_embeddings=True)
    rows = []
    for q, qv in zip(questions, qvecs):
        f, d = file_ranking(vectors, figures, qv, k), db_ranking(index, qv, k)
        same_ids = [a for a, _ in f] == [a for a, _ in d]
        worst = max(abs(a[1] - b[1]) for a, b in zip(f, d)) if len(f) == len(d) else float("inf")
        rows.append({"q": q, "files": f, "db": d, "same_ids": same_ids, "max_diff": worst,
                     "ok": same_ids and worst <= TOLERANCE})
    return rows


def database_metrics(rows):
    """Hit@1, Hit@5, MRR@5 over the answerable questions, rank taken from the database top 5."""
    answerable = [r for r in rows if r["q"]["type"] != "no-answer"]
    ranks = []
    for r in answerable:
        ids = [fig for fig, _ in r["db"]]
        want = r["q"]["figure_number"]
        ranks.append(ids.index(want) + 1 if want in ids else None)
    n = len(ranks)
    return {"n": n, "hits1": sum(1 for x in ranks if x == 1), "hits5": sum(1 for x in ranks if x),
            "Hit@1": sum(1 for x in ranks if x == 1) / n, "Hit@5": sum(1 for x in ranks if x) / n,
            "MRR@5": sum(1 / x for x in ranks if x) / n}


def main():
    rows = compare()
    print(f"{'id':5} {'top-5 figure ids (database)':36} {'same ids':9} {'max |score diff|':>17}")
    for r in rows:
        print(f"{r['q']['id']:5} {' '.join(fig for fig, _ in r['db']):36} "
              f"{'yes' if r['same_ids'] else 'NO':9} {r['max_diff']:>17.2e}")
    bad = [r["q"]["id"] for r in rows if not r["ok"]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} questions identical (same 5 ids in the same order, "
          f"scores within {TOLERANCE:g}); largest score difference {max(r['max_diff'] for r in rows):.2e}")
    if bad:
        print("DIFFERENT:", ", ".join(bad))
    m = database_metrics(rows)
    print(f"\nDatabase, {m['n']} answerable questions: Hit@1 {m['Hit@1']:.3f} ({m['hits1']}/{m['n']})  "
          f"Hit@5 {m['Hit@5']:.3f} ({m['hits5']}/{m['n']})  MRR@5 {m['MRR@5']:.3f}")
    print("EVALUATION.md 3.2 (figure documents, with prefix): Hit@1 0.652 (15/23)  Hit@5 0.870 (20/23)  MRR@5 0.743")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
