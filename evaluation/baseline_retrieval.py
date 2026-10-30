"""Text-only retrieval baseline, no database (SPEC 2.5 embedding model, 5.3 metrics).

Usage (from the repository root):
    python evaluation/baseline_retrieval.py embed    FAA-H-8083-15B BAAI/bge-small-en-v1.5
    python evaluation/baseline_retrieval.py evaluate FAA-H-8083-15B BAAI/bge-small-en-v1.5

embed     encodes the `embed_text` of every chunk in chunks.jsonl, in file order,
          with normalized vectors, and saves them next to the chunks as
          chunk_embeddings_<model>.npy (row i = line i of chunks.jsonl).
evaluate  encodes every question in evaluation/questions.csv, ranks the chunks by
          cosine similarity (a dot product, the vectors are normalized) and
          reports Hit@1, Hit@5 and MRR. Run `embed` first.

A chunk counts as relevant to a question when
  figure: the chunk's `figure_mentions` contains the question's figure_number
          (primary: the paragraph that cites a figure is the text that explains it)
  page:   the chunk's `printed_pages` contains the question's printed_page
          (secondary, looser)
This is a text-only proxy for the figure metrics of SPEC 5.3, which are defined
on figures judged by people. No-answer questions are not scored; their best
cosine score is printed. Hit@5 and MRR look at the top 5 only (MRR is 0 when
nothing relevant is in the top 5, as in SPEC 5.3); MRR over the full ranking is
shown as well.

Output: printed, and saved to evaluation/baseline_results_<model>.txt.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

QUESTIONS = Path("evaluation") / "questions.csv"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # BGE v1.5 retrieval instruction
TOP_K = 5
RULES = ("figure", "page")


def slug(model):
    return model.replace("/", "_")


def paths(handbook_id, model):
    folder = Path("data") / "extracted" / handbook_id
    return folder / "chunks.jsonl", folder / f"chunk_embeddings_{slug(model)}.npy"


def load_chunks(path):
    if not path.exists():
        sys.exit(f"{path} not found: run ingestion/chunk_text.py chunk first.")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def load_questions(handbook_id):
    with open(QUESTIONS, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [r for r in rows if r["handbook"] in ("", handbook_id)]


def load_model(name):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)


def embed(handbook_id, model_name):
    chunks_path, out_path = paths(handbook_id, model_name)
    chunks = load_chunks(chunks_path)
    model = load_model(model_name)
    vectors = model.encode([c["embed_text"] for c in chunks], batch_size=32,
                           normalize_embeddings=True, show_progress_bar=True)
    np.save(out_path, vectors.astype(np.float32))
    longest = max(len(model.tokenizer(c["embed_text"])["input_ids"]) for c in chunks)
    print(f"{len(chunks)} chunks -> {vectors.shape} saved to {out_path}")
    print(f"longest chunk: {longest} tokens (model limit {model.max_seq_length})")


def is_relevant(chunk, question, rule):
    if rule == "figure":
        return question["figure_number"] in chunk["figure_mentions"]
    return question["printed_page"] in chunk["printed_pages"]


def first_hit_rank(order, chunks, question, rule):
    """1-based rank of the first relevant chunk in the full ranking, or None."""
    for rank, i in enumerate(order, 1):
        if is_relevant(chunks[i], question, rule):
            return rank
    return None


def summarize(ranks):
    """Hit@1, Hit@5, MRR over the top 5, MRR over the full ranking (None = no hit)."""
    n = len(ranks)
    top = [r for r in ranks if r is not None and r <= TOP_K]
    return {
        "Hit@1": sum(1 for r in ranks if r == 1) / n,
        f"Hit@{TOP_K}": len(top) / n,
        f"MRR@{TOP_K}": sum(1 / r for r in top) / n,
        "MRR full": sum(1 / r for r in ranks if r is not None) / n,
    }


def table(title, ranks_by_group):
    lines = [title, f"  {'':22} {'n':>3} {'Hit@1':>7} {'Hit@5':>7} {'MRR@5':>7} {'MRR full':>9}"]
    for name, ranks in ranks_by_group.items():
        if not ranks:
            continue
        s = summarize(ranks)
        lines.append(f"  {name:22} {len(ranks):>3} {s['Hit@1']:>7.3f} {s['Hit@5']:>7.3f} "
                     f"{s['MRR@5']:>7.3f} {s['MRR full']:>9.3f}")
    return lines


def evaluate(handbook_id, model_name):
    chunks_path, emb_path = paths(handbook_id, model_name)
    chunks = load_chunks(chunks_path)
    if not emb_path.exists():
        sys.exit(f"{emb_path} not found: run the embed command first.")
    matrix = np.load(emb_path)
    if len(matrix) != len(chunks):
        sys.exit(f"{emb_path.name} has {len(matrix)} rows but chunks.jsonl has {len(chunks)} chunks: "
                 "run embed again.")
    questions = load_questions(handbook_id)
    answerable = [q for q in questions if q["type"] != "no-answer"]
    no_answer = [q for q in questions if q["type"] == "no-answer"]

    cited = {f for c in chunks for f in c["figure_mentions"]}
    pages = {p for c in chunks for p in c["printed_pages"]}
    cannot = {
        "figure": [q["id"] for q in answerable if q["figure_number"] not in cited],
        "page": [q["id"] for q in answerable if q["printed_page"] not in pages],
    }

    model = load_model(model_name)
    out = [f"Baseline retrieval: {handbook_id}, model {model_name}",
           f"{len(chunks)} chunks, {len(answerable)} answerable questions, {len(no_answer)} no-answer",
           "Relevant chunk: figure = cites the expected figure (primary); page = covers the expected printed page",
           ""]
    for rule in RULES:
        ids = cannot[rule]
        out.append(f"Questions that cannot hit under the {rule} rule "
                   f"(no chunk {'cites their figure' if rule == 'figure' else 'covers their page'}): "
                   f"{len(ids)}" + (f" ({', '.join(ids)})" if ids else ""))
    out.append("")

    for label, prefix in (("with BGE query prefix", QUERY_PREFIX), ("without query prefix", "")):
        qvecs = model.encode([prefix + q["question"] for q in answerable], normalize_embeddings=True)
        orders = np.argsort(-(qvecs @ matrix.T), axis=1)
        for rule in RULES:
            ranks = [first_hit_rank(orders[k], chunks, q, rule) for k, q in enumerate(answerable)]
            groups = {"all answerable": ranks}
            for t in sorted({q["type"] for q in answerable}):
                groups[t] = [r for r, q in zip(ranks, answerable) if q["type"] == t]
            out += table(f"[{rule} rule, {label}]", groups)
            out.append("")
            if prefix and rule == "figure":
                detail = []
                for k, q in enumerate(answerable):
                    top = chunks[orders[k][0]]
                    score = float(qvecs[k] @ matrix[orders[k][0]])
                    detail.append(f"  {q['id']} fig {q['figure_number']:>5} rank {str(ranks[k] or '-'):>4}  "
                                  f"top1 {score:.3f} {top['chunk_id'][-5:]} p.{top['printed_pages'][0]} "
                                  f"{' > '.join(top['heading_path'])[:60]}")
                out += ["Per question (figure rule, with prefix): rank of the first relevant chunk, '-' = none",
                        *detail, ""]

    if no_answer:
        qvecs = model.encode([QUERY_PREFIX + q["question"] for q in no_answer], normalize_embeddings=True)
        best = (qvecs @ matrix.T).max(axis=1)
        out.append("No-answer questions: best cosine score (with prefix); compare with the answerable top-1 scores above")
        out += [f"  {q['id']} {s:.3f}  {q['question']}" for q, s in zip(no_answer, best)]

    text = "\n".join(out)
    print(text)
    result_path = Path("evaluation") / f"baseline_results_{slug(model_name)}.txt"
    result_path.write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved to {result_path}")


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("embed", "evaluate"):
        sys.exit("Usage: python evaluation/baseline_retrieval.py embed|evaluate <handbook-id> <model-name>")
    (embed if sys.argv[1] == "embed" else evaluate)(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
