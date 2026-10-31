"""Tests for evaluation/figure_retrieval.py: heading_for, document_text, build_documents.

Run from the repository root:   python -m pytest -q tests/test_figure_retrieval.py

Small made-up figures and chunks whose answers can be worked out by hand. The
model and the embedding are not involved (no download, no GPU). The scoring
functions are tested in test_baseline_retrieval.py.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))
from baseline_retrieval import first_hit_rank  # noqa: E402
from figure_retrieval import build_documents, document_text, heading_for, unique_heading  # noqa: E402


def figure(number="4-2", page="4-3", caption=None, paragraphs=()):
    return {
        "figure_number": number,
        "caption": caption or f"Figure {number}. Some caption.",
        "printed_page": page,
        "referencing_paragraphs": [{"printed_page": page, "text": t} for t in paragraphs],
    }


def chunk(heading, text="Body text.", pages=("4-3",)):
    return {"heading_path": heading, "text": text, "printed_pages": list(pages)}


# ---- unique_heading --------------------------------------------------------

def test_unique_heading_of_one_path():
    assert unique_heading({("Aerodynamics", "Lift")}) == "Aerodynamics > Lift"


def test_unique_heading_of_nothing_is_empty():
    assert unique_heading(set()) == ""


def test_unique_heading_of_two_different_paths_is_empty():
    assert unique_heading({("A",), ("B",)}) == ""


# ---- heading_for -----------------------------------------------------------

def test_heading_comes_from_the_chunk_containing_the_first_reference():
    f = figure(paragraphs=["Lift acts upward [Figure 4-2]."])
    chunks = [chunk(["Forces"], "Intro. Lift acts upward [Figure 4-2]. More."), chunk(["Other"], "Nothing here.")]
    assert heading_for(f, chunks) == "Forces"


def test_heading_path_is_joined_with_arrows():
    f = figure(paragraphs=["See Figure 4-2."])
    assert heading_for(f, [chunk(["Aerodynamics", "Lift"], "See Figure 4-2.")]) == "Aerodynamics > Lift"


def test_only_the_first_reference_decides_the_heading():
    f = figure(paragraphs=["First mention.", "Second mention."])
    chunks = [chunk(["Second"], "Second mention."), chunk(["First"], "First mention.")]
    assert heading_for(f, chunks) == "First"


def test_reference_matching_ignores_line_breaks_and_double_spaces_on_both_sides():
    f = figure(paragraphs=["Lift  acts\nupward."])
    assert heading_for(f, [chunk(["Forces"], "Intro. Lift acts upward.")]) == "Forces"
    assert heading_for(f, [chunk(["Forces"], "Intro.  Lift\nacts  upward.", pages=("9-9",))]) == "Forces"


def test_page_fallback_joins_a_multi_level_heading_with_arrows():
    f = figure(page="4-3")
    assert heading_for(f, [chunk(["Aerodynamics", "Lift"], pages=("4-3",))]) == "Aerodynamics > Lift"


def test_without_references_the_page_decides_when_all_its_chunks_share_a_heading():
    f = figure(page="4-3")
    chunks = [chunk(["Forces"], pages=("4-2", "4-3")), chunk(["Forces"], pages=("4-3",)), chunk(["Far"], pages=("9-9",))]
    assert heading_for(f, chunks) == "Forces"


def test_without_references_and_with_different_headings_on_the_page_the_heading_is_empty():
    f = figure(page="4-3")
    chunks = [chunk(["Forces"], pages=("4-3",)), chunk(["Drag"], pages=("4-3",))]
    assert heading_for(f, chunks) == ""


def test_same_last_heading_but_different_paths_counts_as_different():
    f = figure(page="4-3")
    chunks = [chunk(["A", "Lift"], pages=("4-3",)), chunk(["B", "Lift"], pages=("4-3",))]
    assert heading_for(f, chunks) == ""


def test_no_chunk_on_the_page_gives_an_empty_heading():
    assert heading_for(figure(page="4-3"), [chunk(["Far"], pages=("9-9",))]) == ""


BODY = "Lift acts upward on the wing and is balanced by weight in steady flight, as shown in [Figure 4-2] below."  # > 100 chars


def test_heading_glued_to_the_front_of_the_paragraph_is_skipped_by_looking_at_its_end():
    f = figure(paragraphs=["Forces Lift " + BODY])
    assert len(BODY) > 100
    assert heading_for(f, [chunk(["Forces"], BODY, pages=("9-9",)), chunk(["Other"], "Nope.", pages=("9-9",))]) == "Forces"


def test_the_whole_paragraph_is_tried_before_its_end():
    f = figure(paragraphs=["Forces Lift " + BODY])
    chunks = [chunk(["Forces"], "Forces Lift " + BODY, pages=("9-9",)), chunk(["Other"], BODY, pages=("9-9",))]
    assert heading_for(f, chunks) == "Forces"


def test_only_the_end_of_the_paragraph_is_compared():
    f = figure(paragraphs=[BODY + " Extra words at the end that no chunk has."])
    assert heading_for(f, [chunk(["Forces"], BODY, pages=("9-9",))]) == ""


def test_reference_in_chunks_with_different_headings_does_not_decide():
    f = figure(page="4-3", paragraphs=["Shared sentence."])
    chunks = [chunk(["A"], "Shared sentence.", pages=("9-9",)), chunk(["B"], "Shared sentence.", pages=("9-9",))]
    assert heading_for(f, chunks) == ""


def test_ambiguous_reference_leaves_the_page_to_decide():
    f = figure(page="4-3", paragraphs=["Shared sentence."])
    chunks = [chunk(["A"], "Shared sentence.", pages=("9-9",)), chunk(["B"], "Shared sentence.", pages=("9-9",)),
              chunk(["C"], "Other.", pages=("4-3",))]
    assert heading_for(f, chunks) == "C"


def test_reference_in_several_chunks_with_the_same_heading_decides():
    f = figure(paragraphs=["Shared sentence."])
    chunks = [chunk(["A"], "Shared sentence.", pages=("9-9",)), chunk(["A"], "Shared sentence again.", pages=("9-9",))]
    assert heading_for(f, chunks) == "A"


def test_a_reference_found_in_no_chunk_falls_back_to_the_page():
    f = figure(page="4-3", paragraphs=["Not in any chunk."])
    assert heading_for(f, [chunk(["Forces"], "Other text.", pages=("4-3",))]) == "Forces"


# ---- document_text ---------------------------------------------------------

F = figure(caption="Figure 4-2. Lift.", paragraphs=["Para one.", "Para two."])


def test_full_document_is_heading_caption_then_paragraphs_in_order():
    assert document_text(F, "Forces > Lift") == "Forces > Lift\nFigure 4-2. Lift.\nPara one.\nPara two."


def test_default_variant_is_full():
    assert document_text(F, "H") == document_text(F, "H", "full")


def test_caption_only_variant():
    assert document_text(F, "H", "caption") == "Figure 4-2. Lift."


def test_caption_and_heading_variant_leaves_out_the_paragraphs():
    assert document_text(F, "H", "caption+heading") == "H\nFigure 4-2. Lift."


def test_caption_and_paragraphs_variant_leaves_out_the_heading():
    assert document_text(F, "H", "caption+paragraphs") == "Figure 4-2. Lift.\nPara one.\nPara two."


def test_empty_heading_leaves_no_blank_line():
    assert document_text(F, "") == "Figure 4-2. Lift.\nPara one.\nPara two."


def test_figure_without_references_is_caption_and_heading_only():
    f = figure(caption="Figure 1-1. Airspace.")
    assert document_text(f, "Intro") == "Intro\nFigure 1-1. Airspace."


def test_unknown_variant_is_an_error():
    with pytest.raises(KeyError):
        document_text(F, "H", "nonsense")


# ---- build_documents -------------------------------------------------------

def test_one_document_per_figure_in_figure_order():
    figures = [figure("4-1", "4-1"), figure("4-2", "4-3"), figure("5-1", "5-1")]
    docs = build_documents(figures, [])
    assert [d["figure_number"] for d in docs] == ["4-1", "4-2", "5-1"]


def test_document_carries_what_the_scoring_functions_read():
    d = build_documents([figure("4-2", "4-3")], [])[0]
    assert d["figure_mentions"] == ["4-2"]
    assert d["printed_pages"] == ["4-3"]


def test_document_text_uses_the_heading_found_in_the_chunks():
    f = figure("4-2", "4-3", caption="Figure 4-2. Lift.", paragraphs=["Lift acts upward."])
    d = build_documents([f], [chunk(["Forces"], "Lift acts upward.")])[0]
    assert d["heading"] == "Forces"
    assert d["embed_text"] == "Forces\nFigure 4-2. Lift.\nLift acts upward."


def test_variant_is_passed_through():
    f = figure("4-2", paragraphs=["Lift acts upward."])
    d = build_documents([f], [chunk(["Forces"], "Lift acts upward.")], "caption")[0]
    assert d["embed_text"] == "Figure 4-2. Some caption."
    assert d["heading"] == "Forces"


def test_documents_work_with_first_hit_rank():
    docs = build_documents([figure("4-1"), figure("4-2"), figure("4-3")], [])
    q = {"figure_number": "4-3", "printed_page": "0-0"}
    assert first_hit_rank([2, 0, 1], docs, q, "figure") == 1
    assert first_hit_rank([0, 1, 2], docs, q, "figure") == 3
