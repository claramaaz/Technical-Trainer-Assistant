"""Shared fixtures for the search-slice tests (real data and real model; skipped if the data is absent)."""
import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EMB = ROOT / "data" / "extracted" / "FAA-H-8083-15B" / "figure_embeddings_full_BAAI_bge-small-en-v1.5.npy"


@pytest.fixture(scope="session")
def questions():
    with open(ROOT / "evaluation" / "questions.csv", encoding="utf-8-sig", newline="") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


@pytest.fixture(scope="session")
def real_index():
    if not EMB.exists():
        pytest.skip("data/extracted/... figure embeddings missing: run evaluation/figure_retrieval.py embed")
    from backend.retrieval import load_index
    return load_index()
