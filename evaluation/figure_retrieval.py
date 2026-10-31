"""Figure-level retrieval baseline, no database (SPEC 5.1 figure documents, 5.3 metrics).

Usage (from the repository root):
    python evaluation/figure_retrieval.py embed    FAA-H-8083-15B BAAI/bge-small-en-v1.5
    python evaluation/figure_retrieval.py evaluate FAA-H-8083-15B BAAI/bge-small-en-v1.5

Each figure in figures.jsonl is one search document: its section heading, its
caption and the paragraphs that reference it (SPEC 5.1). The heading is not
stored with the figure; it comes from chunks.jsonl (see heading_for).

embed     encodes the documents of every variant (full, and the ablations without
          the heading and/or the paragraphs) with normalized vectors and saves
          figure_embeddings_<variant>_<model>.npy next to figures.jsonl
          (row i = line i of figures.jsonl).
evaluate  encodes every question in evaluation/questions.csv, ranks the figures by
          cosine similarity and reports Hit@1, Hit@5 and MRR. A figure is a hit
          when its figure_number is the question's expected figure_number. The
          scoring functions are the ones of baseline_retrieval.py (each document
          carries figure_mentions = [its figure number], so the "figure" rule applies).
          No-answer questions are not scored; their best cosine score is printed.

Output: printed, and saved to evaluation/figure_results_<model>.txt.
"""
import json
import sys
from pathlib import Path

import numpy as np

from baseline_retrieval import (QUERY_PREFIX, TOP_K, first_hit_rank, load_model,
                                load_questions, slug, summarize, table)

TAIL = 100  # characters of a referencing paragraph used when the whole paragraph is in no chunk

# What each variant puts in the document, in order.
VARIANTS = {
    "full": ("heading", "caption", "paragraphs"),
    "caption+paragraphs": ("caption", "paragraphs"),
    "caption+heading": ("heading", "caption"),
    "caption": ("caption",),
}


def paths(handbook_id, model, variant="full"):
    folder = Path("data") / "extracted" / handbook_id
    name = f"figure_embeddings_{variant.replace('+', '_')}_{slug(model)}.npy"
    return folder / "figures.jsonl", folder / "chunks.jsonl", folder / name


def load_jsonl(path, hint):
    if not path.exists():
        sys.exit(f"{path} not found: {hint}")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def squash(text):
    return " ".join(text.split())


def unique_heading(headings):
    """'A > B' when all the headings (tuples) are one and the same, else '' (none, or several: no guessing)."""
    return " > ".join(next(iter(headings))) if len(headings) == 1 else ""


def heading_for(figure, chunks):
    """Section heading of a figure, as 'A > B', or '' when it cannot be told.

    First choice: the heading of the chunks that contain the figure's first
    referencing paragraph. In figures.jsonl the heading text is often glued to
    the front of that paragraph, so when the whole paragraph is in no chunk its
    last TAIL characters are looked for instead. If the chunks found have
    different headings, the reference does not decide. Otherwise: the heading
    shared by every chunk that covers the figure's printed page; if those
    chunks have different headings, '' (no guessing).
    """
    refs = figure["referencing_paragraphs"]
    if refs:
        text = squash(refs[0]["text"])
        for target in (text, text[-TAIL:]):
            found = {tuple(c["heading_path"]) for c in chunks if target in squash(c["text"])}
            if len(found) == 1:
                return unique_heading(found)
    return unique_heading({tuple(c["heading_path"]) for c in chunks if figure["printed_page"] in c["printed_pages"]})


def document_text(figure, heading, variant="full"):
    """Searchable text of a figure for a variant: the wanted parts, one per line, empty parts left out."""
    parts = []
    for part in VARIANTS[variant]:
        if part == "heading":
            parts.append(heading)
        elif part == "caption":
            parts.append(figure["caption"])
        else:
            parts.extend(r["text"] for r in figure["referencing_paragraphs"])
    return "\n".join(p for p in parts if p)


def build_documents(figures, chunks, variant="full"):
    """One document per figure, in figures order, shaped for baseline_retrieval's scoring functions."""
    docs = []
    for f in figures:
        heading = heading_for(f, chunks)
        docs.append({
            "figure_number": f["figure_number"],
            "heading": heading,
            "embed_text": document_text(f, heading, variant),
            "figure_mentions": [f["figure_number"]],
            "printed_pages": [f["printed_page"]],
        })
    return docs


def load_all(handbook_id, model_name):
    figures_path, chunks_path, _ = paths(handbook_id, model_name)
    figures = load_jsonl(figures_path, "run ingestion/extract_figures.py first.")
    chunks = load_jsonl(chunks_path, "run ingestion/chunk_text.py chunk first.")
    return figures, chunks


def embed(handbook_id, model_name):
    figures, chunks = load_all(handbook_id, model_name)
    model = load_model(model_name)
    for variant in VARIANTS:
        docs = build_documents(figures, chunks, variant)
        texts = [d["embed_text"] for d in docs]
        vectors = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
        out_path = paths(handbook_id, model_name, variant)[2]
        np.save(out_path, vectors.astype(np.float32))
        lengths = [len(model.tokenizer(t)["input_ids"]) for t in texts]
        over = sum(1 for n in lengths if n > model.max_seq_length)
        print(f"{variant}: {len(docs)} documents -> {vectors.shape} saved to {out_path}")
        print(f"  longest {max(lengths)} tokens (model limit {model.max_seq_length}); "
              f"{over} documents longer than the limit (the end is cut off)")


def evaluate(handbook_id, model_name):
    figures, chunks = load_all(handbook_id, model_name)
    docs = build_documents(figures, chunks)
    matrices = {}
    for variant in VARIANTS:
        emb_path = paths(handbook_id, model_name, variant)[2]
        if not emb_path.exists():
            sys.exit(f"{emb_path} not found: run the embed command first.")
        matrices[variant] = np.load(emb_path)
        if len(matrices[variant]) != len(docs):
            sys.exit(f"{emb_path.name} has {len(matrices[variant])} rows but figures.jsonl has {len(docs)} "
                     "figures: run embed again.")
    questions = load_questions(handbook_id)
    answerable = [q for q in questions if q["type"] != "no-answer"]
    no_answer = [q for q in questions if q["type"] == "no-answer"]
    known = {d["figure_number"] for d in docs}
    cannot = [q["id"] for q in answerable if q["figure_number"] not in known]

    no_refs = sum(1 for f in figures if not f["referencing_paragraphs"])
    no_heading = sum(1 for d in docs if not d["heading"])
    no_heading_refs = sum(1 for d, f in zip(docs, figures) if not d["heading"] and f["referencing_paragraphs"])
    model = load_model(model_name)
    out = [f"Figure document retrieval: {handbook_id}, model {model_name}",
           f"{len(docs)} figure documents, {len(answerable)} answerable questions, {len(no_answer)} no-answer",
           f"Documents without a referencing paragraph: {no_refs}; without a heading: {no_heading} "
           f"({no_heading_refs} of them have referencing paragraphs)",
           "Relevant figure: its figure_number is the question's expected figure_number",
           f"Questions that cannot hit (figure not in figures.jsonl): {len(cannot)}"
           + (f" ({', '.join(cannot)})" if cannot else ""),
           ""]

    def ranks_for(variant, prefix):
        qvecs = model.encode([prefix + q["question"] for q in answerable], normalize_embeddings=True)
        scores = qvecs @ matrices[variant].T
        orders = np.argsort(-scores, axis=1)
        return [first_hit_rank(orders[k], docs, q, "figure") for k, q in enumerate(answerable)], orders, scores

    for label, prefix in (("with BGE query prefix", QUERY_PREFIX), ("without query prefix", "")):
        ranks, orders, scores = ranks_for("full", prefix)
        groups = {"all answerable": ranks}
        for t in sorted({q["type"] for q in answerable}):
            groups[t] = [r for r, q in zip(ranks, answerable) if q["type"] == t]
        out += table(f"[full document, {label}]", groups)
        out.append("")
        if prefix:
            detail = [f"  {q['id']} fig {q['figure_number']:>5} rank {str(ranks[k] or '-'):>4}  "
                      f"top1 {scores[k][orders[k][0]]:.3f} fig {docs[orders[k][0]]['figure_number']:>5}"
                      for k, q in enumerate(answerable)]
            out += ["Per question (full document, with prefix): rank of the expected figure, '-' = none",
                    *detail, ""]

    for label, prefix in (("with BGE query prefix", QUERY_PREFIX), ("without query prefix", "")):
        out += table(f"[ablation, {label}: what goes into the document]",
                     {v: ranks_for(v, prefix)[0] for v in VARIANTS})
        out.append("")

    if no_answer:
        qvecs = model.encode([QUERY_PREFIX + q["question"] for q in no_answer], normalize_embeddings=True)
        best = (qvecs @ matrices["full"].T).max(axis=1)
        out.append("No-answer questions: best cosine score (full document, with prefix); "
                   "compare with the answerable top-1 scores above")
        out += [f"  {q['id']} {s:.3f}  {q['question']}" for q, s in zip(no_answer, best)]

    text = "\n".join(out)
    print(text)
    result_path = Path("evaluation") / f"figure_results_{slug(model_name)}.txt"
    result_path.write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved to {result_path}")


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("embed", "evaluate"):
        sys.exit("Usage: python evaluation/figure_retrieval.py embed|evaluate <handbook-id> <model-name>")
    (embed if sys.argv[1] == "embed" else evaluate)(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
