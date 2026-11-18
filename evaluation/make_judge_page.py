"""Build a local HTML page to judge the pending pairs of judgements.csv (SPEC 5.3).

Usage:
  python evaluation/make_judge_page.py build Clara Q001 Q025   -> evaluation/judge_Clara.html
  python evaluation/make_judge_page.py merge Clara <downloaded csv>  -> fills judgements.csv

The page shows the question and the returned figure (image + caption) only:
no rank, no similarity score, so the judge is not influenced by the system.
"""
import csv, html, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUDGEMENTS = ROOT / "evaluation" / "judgements.csv"
QUESTIONS = ROOT / "evaluation" / "questions.csv"


def load_figures():
    figs = {}
    for hb in ("FAA-H-8083-15B", "FAA-H-8083-25C"):
        for line in open(ROOT / "data" / "extracted" / hb / "figures.jsonl", encoding="utf-8"):
            f = json.loads(line)
            figs[(hb, f["figure_number"])] = f
    return figs


def qnum(qid):
    return int(qid[1:])


def build(judge, first, last):
    qs = {r["id"]: r for r in csv.DictReader(open(QUESTIONS, encoding="utf-8"))}
    figs = load_figures()
    rows = [r for r in csv.DictReader(open(JUDGEMENTS, encoding="utf-8"))
            if not r["score"] and qnum(first) <= qnum(r["question_id"]) <= qnum(last)]
    items = []
    for r in rows:
        f = figs.get((r["handbook_id"], r["figure_number"]), {})
        q = qs[r["question_id"]]
        exp = figs.get((q["handbook"], q["figure_number"]), {})
        items.append({
            "key": f'{r["question_id"]}|{r["handbook_id"]}|{r["figure_number"]}',
            "q": f'{r["question_id"]} ({q["type"]}): {q["question"]}',
            "img": f'../data/extracted/{r["handbook_id"]}/{f.get("image_path", "")}',
            "cap": f'{r["handbook_id"]} - {f.get("caption", "(no caption)")} (page {f.get("printed_page", "?")})',
            "exp_img": f'../data/extracted/{q["handbook"]}/{exp.get("image_path", "")}',
            "exp_cap": f'Expected: {q["handbook"]} - {exp.get("caption", "")}',
        })
    page = TEMPLATE.replace("__JUDGE__", html.escape(judge)).replace("__DATA__", json.dumps(items))
    out = ROOT / "evaluation" / f"judge_{judge}.html"
    out.write_text(page, encoding="utf-8")
    print(f"{len(items)} pairs -> {out}")


def merge(judge, path):
    done = {r["key"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}
    rows = list(csv.DictReader(open(JUDGEMENTS, encoding="utf-8")))
    n = 0
    for r in rows:
        k = f'{r["question_id"]}|{r["handbook_id"]}|{r["figure_number"]}'
        if k in done and not r["score"] and done[k]["score"] in ("0", "1", "2"):
            r["score"], r["judge"], r["note"] = done[k]["score"], judge, done[k]["note"]
            n += 1
    with open(JUDGEMENTS, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["question_id", "handbook_id", "figure_number", "score", "judge", "note"])
        w.writeheader(); w.writerows(rows)
    print(f"{n} judgements written to {JUDGEMENTS}")


TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Judge __JUDGE__</title>
<style>body{font-family:sans-serif;margin:16px;max-width:1300px}#q{font-size:22px;font-weight:bold;margin:8px 0}
.row{display:flex;gap:16px}.col{flex:1}img{max-width:100%;max-height:60vh;border:1px solid #ccc}
.exp img{max-height:30vh;opacity:.85}button{font-size:20px;padding:10px 22px;margin:4px}
#note{width:60%;font-size:16px}.small{color:#555}</style></head><body>
<div class="small">Judge: __JUDGE__ — <span id="pos"></span> — keys: 2 / 1 / 0, ← back. Progress is saved in the browser.</div>
<div id="q"></div>
<div class="row"><div class="col"><b>Returned figure</b><br><img id="img"><div id="cap"></div></div>
<div class="col exp"><b>Reference (score-2 example)</b><br><img id="eimg"><div id="ecap" class="small"></div></div></div>
<p><b>Does this returned figure answer the question?</b>
2 = as good as the expected figure · 1 = related, but not the answer · 0 = not relevant</p>
<button onclick="put('2')">2</button><button onclick="put('1')">1</button><button onclick="put('0')">0</button>
<button onclick="go(-1)">← back</button> Note: <input id="note" placeholder="one-line reason (required for 1, and for 2)">
<p><button onclick="exportCsv()">Export CSV (when finished)</button> <span id="cur"></span></p>
<script>
const D=__DATA__, K='judge___JUDGE__';let S=JSON.parse(localStorage.getItem(K)||'{}'),i=0;
while(i<D.length-1&&S[D[i].key])i++;
function show(){const d=D[i];q.textContent=d.q;img.src=d.img;cap.textContent=d.cap;eimg.src=d.exp_img;ecap.textContent=d.exp_cap;
 note.value=S[d.key]?S[d.key].note:'';pos.textContent=(i+1)+' / '+D.length+' — judged '+Object.keys(S).length;
 cur.textContent=S[d.key]?('current score: '+S[d.key].score):'';}
function put(s){S[D[i].key]={score:s,note:note.value};localStorage.setItem(K,JSON.stringify(S));if(i<D.length-1)i++;show();}
function go(n){i=Math.max(0,Math.min(D.length-1,i+n));show();}
document.addEventListener('keydown',e=>{if(e.target===note)return;if('012'.includes(e.key)&&e.key)put(e.key);if(e.key==='ArrowLeft')go(-1);});
function exportCsv(){let t='key,score,note\n';for(const k in S)t+=k+','+S[k].score+',"'+S[k].note.replace(/"/g,'""')+'"\n';
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([t],{type:'text/csv'}));a.download='judged___JUDGE__.csv';a.click();}
show();
</script></body></html>"""

if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        merge(sys.argv[2], sys.argv[3])
