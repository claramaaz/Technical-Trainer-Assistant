"""Tests for the joint text + image retrieval of backend/retrieval.py (P7-30), written from brief
section 4 ("Joint retrieval over text and images") and SPEC FR-002 / BR-001.

No database and no model: the text ranking is a fake index ranked with numpy (tests/fake_index.py),
the image ranking is a fixed list. Run:   python -m pytest -q tests/test_joint_retrieval.py
"""
import re

import numpy as np
import pytest

from backend import retrieval
from backend.retrieval import NO_ANSWER, fuse_rrf, retrieve
from fake_index import make_fake


def test_a_figure_found_by_both_lists_beats_a_figure_first_in_only_one():
    text = [(1, 0.9), (2, 0.8), (3, 0.7)]
    image = [(4, 0.3), (2, 0.29), (5, 0.28)]
    fused = fuse_rrf([text, image], k=3)
    assert fused[0][0] == 2                       # 2nd in both lists: 1/62 + 1/62
    assert fused[0][1] == pytest.approx(2 / 62)
    assert {fid for fid, _ in fused[1:]} == {1, 4}  # 1st in one list only: 1/61


def test_fusion_uses_ranks_not_scores():
    # The image scores are 100 times larger, but only the positions count.
    small = fuse_rrf([[(1, 0.9), (2, 0.1)], [(2, 90.0), (1, 10.0)]], k=2)
    assert small[0][1] == pytest.approx(small[1][1])
    assert [fid for fid, _ in small] == [1, 2]    # a tie: the smaller id first, always the same order


def test_fusion_returns_at_most_k_figures():
    assert len(fuse_rrf([[(i, 1.0) for i in range(10)]], k=5)) == 5


def test_mode_from_environment_then_env_file_then_default(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("RETRIEVAL_MODE=image\n", encoding="utf-8")
    assert retrieval.retrieval_mode({"RETRIEVAL_MODE": "Joint"}, env_file) == "joint"
    assert retrieval.retrieval_mode({}, env_file) == "image"
    assert retrieval.retrieval_mode({}, tmp_path / "missing.env") == "text"


def test_unknown_mode_stops():
    with pytest.raises(ValueError):
        retrieval.retrieval_mode({"RETRIEVAL_MODE": "clip"}, None)


def doc(number):
    return {"figure_number": number, "caption": f"Figure {number}.", "image_path": None, "passage": "",
            "printed_page": number, "handbook_id": "HB-A", "handbook": "HB-A"}


@pytest.fixture
def index():
    # Text similarities with the question [1, 0]: id 0 -> 0.90, id 1 -> 0.80, id 2 -> 0.10
    return make_fake([doc("1-1"), doc("1-2"), doc("1-3")], np.array([[0.9, 0.0], [0.8, 0.0], [0.1, 0.0]]))


def use_image_ranking(monkeypatch, ranked):
    """The image ranking becomes the fixed list `ranked`. Text scores of any id come from the fake."""
    monkeypatch.setattr(retrieval, "embed_image_query", lambda query: "clip vector")
    monkeypatch.setattr(retrieval, "rank_image", lambda idx, vec, k, handbooks=None: ranked[:k])
    monkeypatch.setattr(retrieval, "text_scores",
                        lambda idx, q, ids: {i: float(idx.vectors[i] @ q) for i in ids})


@pytest.fixture
def image_list(monkeypatch, index):
    # The image ranking puts figure 2 first, then figure 1, then figure 0 (the reverse of the text).
    use_image_ranking(monkeypatch, [(2, 0.31), (1, 0.30), (0, 0.10)])


def ids(found):
    return [r["id"] for r in found["results"]]


def test_text_mode_is_the_old_search(index, image_list):
    found = retrieve("q", k=3, index=index, query_vector=np.array([1.0, 0.0]), mode="text")
    assert ids(found) == [0, 1, 2]


def test_joint_mode_lets_the_image_move_a_figure_up(index, monkeypatch):
    # Text: 0, 1, 2. Image: 1, 2, 0. Figure 1 is 2nd by text but 1st by image: it comes first.
    use_image_ranking(monkeypatch, [(1, 0.31), (2, 0.30), (0, 0.10)])
    found = retrieve("q", k=3, index=index, query_vector=np.array([1.0, 0.0]), mode="joint")
    assert ids(found) == [1, 0, 2]     # fused: 1/62 + 1/61  >  1/61 + 1/63  >  1/63 + 1/62


def test_score_shown_is_always_the_text_similarity(index, image_list):
    found = retrieve("q", k=3, index=index, query_vector=np.array([1.0, 0.0]), mode="image")
    assert ids(found) == [2, 1, 0]
    assert [r["score"] for r in found["results"]] == pytest.approx([0.10, 0.80, 0.90])


def test_threshold_uses_the_best_text_match_in_every_mode(index, image_list):
    # Best text similarity 0.9 * 0.5 = 0.45 < THRESHOLD: no answer, even if an image ranks first.
    for mode in ("text", "image", "joint"):
        found = retrieve("q", k=3, index=index, query_vector=np.array([0.5, 0.0]), mode=mode)
        assert found == {"results": [], "reason": NO_ANSWER}


def test_image_search_reads_only_the_searchable_views():
    sql = retrieval.IMAGE_RANK_SQL + retrieval.TEXT_SCORE_SQL
    tables = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql, flags=re.I))
    assert tables == {"searchable_figure_images", "searchable_figures"}


# --- passages (chunks) -> figures: the "passages" and "hybrid" modes ---------------------------------

def test_a_chunk_gives_its_score_to_the_figures_it_cites(index):
    chunks = [("HB-A", ["1-2"], 0.80), ("HB-A", ["1-1", "1-2"], 0.70)]
    # ids: 1-1 -> 0, 1-2 -> 1. Figure 1-2 keeps its best chunk (0.80), figure 1-1 gets 0.70.
    assert retrieval.figures_from_chunks(chunks, index) == [(1, 0.80), (0, 0.70)]


def test_a_mention_of_an_unknown_figure_or_of_another_handbook_is_ignored(index):
    chunks = [("HB-A", ["9-9"], 0.90), ("HB-B", ["1-1"], 0.90), ("HB-A", ["1-3"], 0.50)]
    assert retrieval.figures_from_chunks(chunks, index) == [(2, 0.50)]


def use_passage_ranking(monkeypatch, ranked):
    monkeypatch.setattr(retrieval, "rank_chunks", lambda idx, q, k, handbooks=None: ranked[:k])
    monkeypatch.setattr(retrieval, "text_scores", lambda idx, q, ids: {i: float(idx.vectors[i] @ q) for i in ids})


def test_passages_mode_follows_the_chunks_and_shows_the_text_score(index, monkeypatch):
    use_passage_ranking(monkeypatch, [(2, 0.60), (0, 0.55)])
    found = retrieve("q", k=2, index=index, query_vector=np.array([1.0, 0.0]), mode="passages")
    assert ids(found) == [2, 0]
    assert [r["score"] for r in found["results"]] == pytest.approx([0.10, 0.90])


def test_hybrid_mode_fuses_figure_text_and_passages(index, monkeypatch):
    # Text order: 0, 1, 2. Passages order: 1, 2 (figure 0 is cited by no chunk).
    use_passage_ranking(monkeypatch, [(1, 0.60), (2, 0.55)])
    found = retrieve("q", k=3, index=index, query_vector=np.array([1.0, 0.0]), mode="hybrid")
    # fused: figure 1 = 1/62 + 1/61, figure 2 = 1/63 + 1/62, figure 0 = 1/61 only
    assert ids(found) == [1, 2, 0]


def test_threshold_still_uses_the_best_text_match_with_passages(index, monkeypatch):
    use_passage_ranking(monkeypatch, [(2, 0.99)])
    for mode in ("passages", "hybrid"):
        found = retrieve("q", k=3, index=index, query_vector=np.array([0.5, 0.0]), mode=mode)
        assert found == {"results": [], "reason": NO_ANSWER}


def test_chunk_search_reads_only_the_searchable_view():
    tables = set(re.findall(r"(?:FROM|JOIN)\s+(\w+)", retrieval.CHUNK_RANK_SQL, flags=re.I))
    assert tables == {"searchable_chunks"}
