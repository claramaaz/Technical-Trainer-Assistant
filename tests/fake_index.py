"""An in-memory search index for tests that need exact scores and no database."""
from dataclasses import dataclass

import numpy as np

from backend.retrieval import Index


@dataclass
class FakeIndex(Index):
    """Documents in memory; row i has cosine similarity vectors[i] @ query with the question."""
    vectors: object = None


def numpy_rank(index, query_vector, k):
    scores = index.vectors @ query_vector
    return [(int(i), float(scores[i])) for i in np.argsort(-scores)[:k]]


def make_fake(documents, vectors, handbook="Test Handbook"):
    """documents: list of dicts (row i = vectors[i]). Keyed by row number like database ids."""
    return FakeIndex(dict(enumerate(documents)), handbook, "no database", vectors)
