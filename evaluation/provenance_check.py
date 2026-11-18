"""Provenance check (SPEC 5.3): is the cited page the page where the returned figure appears?

Usage (from the repository root):
  python evaluation/provenance_check.py build <run label> [--n 30] [--seed 5]
      -> evaluation/provenance_<label>.html  (page images + y/n buttons) and a script pre-check
  python evaluation/provenance_check.py merge <label> <downloaded csv>
      -> evaluation/provenance_<label>.csv   (judged sample, the evidence) and the result

Sample: figures that the system returned FIRST for an answerable question (scope "all", the real
search), one row per distinct figure, drawn at random (seed). The "cited page" is the printed page
the system shows next to the figure (printed_page of ranked.csv, which comes from the database).

Script pre-check (it helps, it does not replace the human judgement):
  figure_on_page : the PDF page text contains the caption number "Figure N-N."
  number_on_page : the cited printed page appears as a standalone line in the page text
The human judges on the page image: the figure is on that page and the number printed in the
header/footer is the cited one.
"""
import csv
import html
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "evaluation" / "runs"


def load_figures():
    figs = {}
    for hb in ("FAA-H-8083-15B", "FAA-H-8083-25C"):
        for line in open(ROOT / "data" / "extracted" / hb / "figures.jsonl", encoding="utf-8"):
            f = json.loads(line)
            figs[(hb, f["figure_number"])] = f
    return figs


def returned_first(label):
    rows = list(csv.DictReader(open(RUNS / label / "ranked.csv", encoding="utf-8")))
    seen, out = set(), []
    for r in rows:
        if r["scope"] == "all" and r["answered"] == "1" and r["rank"] == "1":
            key = (r["handbook_id"], r["figure_number"])
            if key not in seen:
                seen.add(key)
                out.append(r)
    return out


def page_texts(handbook, pages):
    from pypdf import PdfReader
    reader = PdfReader(str(ROOT / "data" / "raw" / f"{handbook}.pdf"))
    return {p: (reader.pages[p - 1].extract_text() or "") for p in pages}


def pre_check(fig, cited, text):
    lines = [ln.strip() for ln in text.splitlines()]
    return {
        "figure_on_page": "y" if re.search(r"Figure\s+" + re.escape(fig["figure_number"]) + r"\.", text) else "n",
        "number_on_page": "y" if cited in lines else "n",
    }


def build(label, n, seed):
    figs = load_figures()
    pool = returned_first(label)
    if len(pool) < n:
        n = len(pool)
    sample = random.Random(seed).sample(pool, n)
    sample.sort(key=lambda r: (r["handbook_id"], int(figs[(r["handbook_id"], r["figure_number"])]["pdf_page"])))
    items = []
    for r in sample:
        f = figs[(r["handbook_id"], r["figure_number"])]
        items.append((r, f))
    texts = {}
    for hb in {r["handbook_id"] for r, _ in items}:
        pages = [f["pdf_page"] for r, f in items if r["handbook_id"] == hb]
        texts[hb] = page_texts(hb, pages)
    cards, summary = [], []
    for i, (r, f) in enumerate(items):
        auto = pre_check(f, r["printed_page"], texts[r["handbook_id"]][f["pdf_page"]])
        same = "y" if r["printed_page"] == f["printed_page"] else "n"
        summary.append((r, f, auto, same))
        img = f"../data/extracted/{r['handbook_id']}/pages/p{f['pdf_page']:04d}.jpg"
        cards.append(
            f"<div class=c data-hb='{r['handbook_id']}' data-fig='{html.escape(r['figure_number'])}' "
            f"data-cited='{html.escape(r['printed_page'])}' data-pdf='{f['pdf_page']}' "
            f"data-fa='{auto['figure_on_page']}' data-na='{auto['number_on_page']}'>"
            f"<h3>{i + 1}. {r['handbook_id']} - Figure {html.escape(r['figure_number'])}</h3>"
            f"<p>The system cites: <b>page {html.escape(r['printed_page'])}</b> "
            f"(PDF page {f['pdf_page']}). Is the figure on this page, and is this the number printed on it?</p>"
            f"<img src='{img}'><p>"
            f"<label><input type=radio name=q{i} value=y> y</label> "
            f"<label><input type=radio name=q{i} value=n> n</label> "
            f"<input class=note placeholder='note'></p></div>")
    page = (
        "<meta charset=utf-8><title>Provenance check</title><style>body{font-family:sans-serif;max-width:900px;"
        "margin:auto}.c{border:1px solid #ccc;margin:14px 0;padding:8px}img{max-width:100%;max-height:650px}"
        "button{font-size:16px;padding:8px 14px}</style>"
        f"<h1>Provenance check ({label}, n={len(items)}, seed {seed})</h1>"
        "<p>For each card, look at the page: y = the figure is on this page AND the page number printed "
        "in its header/footer is the cited one; n otherwise.</p>" + "".join(cards) +
        "<button onclick='exportCsv()'>Export CSV</button><script>"
        "function exportCsv(){const rows=[['handbook_id','figure_number','cited_page','pdf_page',"
        "'figure_on_page_auto','number_on_page_auto','page_correct','notes']];"
        "document.querySelectorAll('.c').forEach((c,i)=>{const v=c.querySelector('input[type=radio]:checked');"
        "rows.push([c.dataset.hb,c.dataset.fig,c.dataset.cited,c.dataset.pdf,c.dataset.fa,c.dataset.na,"
        "v?v.value:'',c.querySelector('.note').value]);});"
        "const t=rows.map(r=>r.map(x=>'\"'+String(x).replace(/\"/g,'\"\"')+'\"').join(',')).join('\\n');"
        "const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\\ufeff'+t],{type:'text/csv'}));"
        "a.download='provenance_judged.csv';a.click();}</script>")
    out = ROOT / "evaluation" / f"provenance_{label}.html"
    out.write_text(page, encoding="utf-8")
    ok_fig = sum(1 for _, _, a, _ in summary if a["figure_on_page"] == "y")
    ok_num = sum(1 for _, _, a, _ in summary if a["number_on_page"] == "y")
    same = sum(1 for *_, s in summary if s == "y")
    print(f"Wrote {out} ({len(items)} figures drawn from {len(pool)} distinct first-ranked figures)")
    print(f"Script pre-check: figure caption on the PDF page {ok_fig}/{len(items)}; "
          f"cited number found as a line on the page {ok_num}/{len(items)}; "
          f"cited page = printed page in figures.jsonl {same}/{len(items)}")
    for r, f, a, s in summary:
        if a["figure_on_page"] != "y" or a["number_on_page"] != "y" or s != "y":
            print("  to look at:", r["handbook_id"], r["figure_number"], "cited", r["printed_page"],
                  "pdf", f["pdf_page"], a, "jsonl", f["printed_page"])


def merge(label, path):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    blank = [r["figure_number"] for r in rows if r["page_correct"].strip().lower() not in ("y", "n")]
    if blank:
        sys.exit(f"{len(blank)} figures have no y/n: {', '.join(blank)}")
    out = ROOT / "evaluation" / f"provenance_{label}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["page_correct"].strip().lower() == "y")
    print(f"Provenance correctness: {ok}/{len(rows)} = {ok / len(rows):.0%} (saved {out})")
    print("Wrong:", ", ".join(f"{r['handbook_id']} {r['figure_number']}" for r in rows
                              if r["page_correct"].strip().lower() == "n") or "none")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 2 and a[0] == "build":
        n = int(a[a.index("--n") + 1]) if "--n" in a else 30
        seed = int(a[a.index("--seed") + 1]) if "--seed" in a else 5
        build(a[1], n, seed)
    elif len(a) == 3 and a[0] == "merge":
        merge(a[1], a[2])
    else:
        print(__doc__)
