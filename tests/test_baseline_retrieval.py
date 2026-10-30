"""Tests for evaluation/baseline_retrieval.py: is_relevant, first_hit_rank, summarize.

Run from the repository root:   python -m pytest -q tests/test_baseline_retrieval.py

Only the scoring functions are tested, with small made-up chunks and rankings
whose answers can be worked out by hand. The embedding and the model are not
involved (no download, no GPU).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))
from baseline_retrieval import first_hit_rank, is_relevant, summarize  # noqa: E402


def chunk(figures=(), pages=("1-1",)):
    return {"figure_mentions": list(figures), "printed_pages": list(pages)}


def question(figure="4-2", page="4-3"):
    return {"figure_number": figure, "printed_page": page}


# ---- is_relevant -----------------------------------------------------------

def test_figure_rule_needs_the_exact_figure_number():
    q = question(figure="4-2")
    assert is_relevant(chunk(figures=["4-1", "4-2"]), q, "figure")
    assert not is_relevant(chunk(figures=["4-1", "4-3"]), q, "figure")
    assert not is_relevant(chunk(figures=[]), q, "figure")


def test_figure_rule_does_not_match_a_longer_number():
    # "4-2" must not match "4-20" or "14-2"
    assert not is_relevant(chunk(figures=["4-20", "14-2"]), question(figure="4-2"), "figure")


def test_page_rule_needs_the_page_among_the_chunks_pages():
    q = question(page="4-3")
    assert is_relevant(chunk(pages=["4-2", "4-3"]), q, "page")
    assert not is_relevant(chunk(pages=["4-2", "4-4"]), q, "page")


def test_the_two_rules_are_independent():
    q = question(figure="4-2", page="4-3")
    cites_figure_only = chunk(figures=["4-2"], pages=["9-9"])
    on_page_only = chunk(figures=["7-7"], pages=["4-3"])
    assert is_relevant(cites_figure_only, q, "figure") and not is_relevant(cites_figure_only, q, "page")
    assert is_relevant(on_page_only, q, "page") and not is_relevant(on_page_only, q, "figure")


# ---- first_hit_rank --------------------------------------------------------

CHUNKS = [
    chunk(figures=["1-1"]),   # 0
    chunk(figures=["4-2"]),   # 1  relevant
    chunk(figures=["2-2"]),   # 2
    chunk(figures=["4-2"]),   # 3  relevant
    chunk(figures=["3-3"]),   # 4
]


def test_rank_follows_the_ranking_order_not_the_chunk_numbers():
    q = question(figure="4-2")
    assert first_hit_rank([1, 0, 2, 3, 4], CHUNKS, q, "figure") == 1
    assert first_hit_rank([0, 2, 4, 1, 3], CHUNKS, q, "figure") == 4   # chunk 1 sits in 4th place
    assert first_hit_rank([4, 3, 1, 2, 0], CHUNKS, q, "figure") == 2   # chunk 3 comes first


def test_rank_is_the_first_of_several_relevant_chunks():
    assert first_hit_rank([0, 2, 3, 1, 4], CHUNKS, question(figure="4-2"), "figure") == 3


def test_rank_is_none_when_nothing_is_relevant():
    assert first_hit_rank([0, 1, 2, 3, 4], CHUNKS, question(figure="9-9"), "figure") is None


def test_rank_can_be_beyond_the_top_5_and_counts_from_one():
    many = [chunk(figures=["x"]) for _ in range(9)] + [chunk(figures=["4-2"])]
    assert first_hit_rank(list(range(10)), many, question(figure="4-2"), "figure") == 10
    assert first_hit_rank([9, 0], many, question(figure="4-2"), "figure") == 1


def test_rank_uses_the_chosen_rule():
    chunks = [chunk(figures=["4-2"], pages=["1-1"]), chunk(figures=[], pages=["4-3"])]
    q = question(figure="4-2", page="4-3")
    assert first_hit_rank([0, 1], chunks, q, "figure") == 1
    assert first_hit_rank([0, 1], chunks, q, "page") == 2


# ---- summarize -------------------------------------------------------------

def test_summarize_worked_example():
    # five questions: found at rank 1, 2, 5, 6 and not found
    s = summarize([1, 2, None, 6, 5])
    assert s["Hit@1"] == pytest.approx(1 / 5)
    assert s["Hit@5"] == pytest.approx(3 / 5)                       # ranks 1, 2, 5; rank 6 is outside
    assert s["MRR@5"] == pytest.approx((1 + 1 / 2 + 1 / 5) / 5)     # rank 6 and None count 0
    assert s["MRR full"] == pytest.approx((1 + 1 / 2 + 1 / 6 + 1 / 5) / 5)


def test_summarize_rank_5_is_in_the_top_5_and_rank_6_is_not():
    assert summarize([5])["Hit@5"] == 1
    assert summarize([6])["Hit@5"] == 0
    assert summarize([6])["MRR@5"] == 0
    assert summarize([6])["MRR full"] == pytest.approx(1 / 6)


def test_summarize_all_found_first_gives_perfect_scores():
    s = summarize([1, 1, 1])
    assert (s["Hit@1"], s["Hit@5"], s["MRR@5"], s["MRR full"]) == (1, 1, 1, 1)


def test_summarize_nothing_found_gives_zeros():
    s = summarize([None, None])
    assert (s["Hit@1"], s["Hit@5"], s["MRR@5"], s["MRR full"]) == (0, 0, 0, 0)


def test_summarize_hit_at_1_ignores_rank_2():
    assert summarize([2, 2])["Hit@1"] == 0
