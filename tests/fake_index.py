"""An in-memory search index for tests that need exact scores and no database."""
from dataclasses import dataclass

import numpy as np

from backend.retrieval import Index


@dataclass
class FakeIndex(Index):
    """Documents in memory; row i has cosine similarity vectors[i] @ query with the question."""
    vectors: object = None


def numpy_rank(index, query_vector, k, handbooks=None):
    scores = index.vectors @ query_vector
    order = [int(i) for i in np.argsort(-scores)
             if handbooks is None or index.documents[int(i)]["handbook_id"] in handbooks]
    return [(i, float(scores[i])) for i in order[:k]]


def make_fake(documents, vectors, handbook="Test Handbook"):
    """documents: list of dicts (row i = vectors[i]). Keyed by row number like database ids.
    A document without its own handbook gets the default one."""
    for d in documents:
        d.setdefault("handbook", handbook)
        d.setdefault("handbook_id", "TEST")
    return FakeIndex(dict(enumerate(documents)), "no database", vectors)
