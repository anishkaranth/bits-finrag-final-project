"""Compact hand-built SVG charts (small, text-friendly versions of the matplotlib PNGs)."""
import json, sys, types
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"; IMG = R / "images"
TEAL, RED, GREY = "#0f766e", "#dc2626", "#64748b"
PAL = ["#0f766e", "#2563eb", "#d97706", "#7c3aed", "#db2777"]

def _svg(w, h, body, title):
    lines = title.split("\n")
    t = "".join(f'<text x="{w/2}" y="{18+i*16}" text-anchor="middle" font-size="{13 if i==0 else 11}" fill="#0f172a">{escape(l)}</text>' for i, l in enumerate(lines))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">'
            f'<rect width="{w}" height="{h}" fill="#fff"/>{t}{body}</svg>\n')

def hbar(name, items, title, xmax, label_w=330, w=900, bar_h=18, gap=6, top=None, legend=""):
    top = top or (30 + 16 * title.count("\n") + 12)
    h = top + len(items) * (bar_h + gap) + 30
    pw = w - label_w - 150; b = []
    for i, (lab, val, col, ann) in enumerate(items):
        y = top + i * (bar_h + gap); bw = pw * val / xmax
        b.append(f'<text x="{label_w-8}" y="{y+bar_h-5}" text-anchor="end" font-size="11">{escape(lab)}</text>')
        b.append(f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{col}"/>')
        b.append(f'<text x="{label_w+bw+5:.1f}" y="{y+bar_h-5}" font-size="10" fill="{GREY}">{escape(ann)}</text>')
    b.append(f'<line x1="{label_w}" y1="{top-4}" x2="{label_w}" y2="{h-30}" stroke="#94a3b8"/>')
    if legend: b.append(f'<text x="{w/2}" y="{h-10}" text-anchor="middle" font-size="10" fill="{GREY}">{escape(legend)}</text>')
    (IMG / f"{name}.svg").write_text(_svg(w, h, "".join(b), title))

def vbar(name, cats, series, title, ymin=0.0, ymax=1.0, w=760, h=380, errs=None, fmt="{:.2f}", ylab=""):
    top = 30 + 16 * title.count("\n") + 20; left, bottom = 60, 50
    ph = h - top - bottom; pw = w - left - 20
    gw = pw / len(cats); bw = gw * 0.8 / len(series); b = []
    sy = lambda v: top + ph - ph * (v - ymin) / (ymax - ymin)
    for k in range(6):
        v = ymin + (ymax - ymin) * k / 5; y = sy(v)
        b.append(f'<line x1="{left}" y1="{y:.1f}" x2="{w-20}" y2="{y:.1f}" stroke="#e2e8f0"/><text x="{left-5}" y="{y+4:.1f}" text-anchor="end" font-size="10">{fmt.format(v)}</text>')
    for si, (sname, vals, col) in enumerate(series):
        for ci, v in enumerate(vals):
            x = left + ci * gw + gw * 0.1 + si * bw; y = sy(v)
            b.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{top+ph-y:.1f}" fill="{col}"/>')
            if len(series) == 1: b.append(f'<text x="{x+bw/2:.1f}" y="{y-4:.1f}" text-anchor="middle" font-size="10">{fmt.format(v)}</text>')
            if errs:
                lo, hi = errs[ci]; xm = x + bw / 2
                b.append(f'<line x1="{xm:.1f}" y1="{sy(lo):.1f}" x2="{xm:.1f}" y2="{sy(hi):.1f}" stroke="#0f172a"/>')
    for ci, c in enumerate(cats):
        b.append(f'<text x="{left+ci*gw+gw/2:.1f}" y="{top+ph+16}" text-anchor="middle" font-size="10">{escape(c)}</text>')
    if len(series) > 1:
        for si, (sname, _, col) in enumerate(series):
            x = left + si * (pw / len(series))
            b.append(f'<rect x="{x:.1f}" y="{h-20}" width="10" height="10" fill="{col}"/><text x="{x+14:.1f}" y="{h-11}" font-size="10">{escape(sname)}</text>')
    if ylab: b.append(f'<text x="14" y="{top+ph/2}" font-size="10" transform="rotate(-90 14 {top+ph/2})" text-anchor="middle">{escape(ylab)}</text>')
    (IMG / f"{name}.svg").write_text(_svg(w, h, "".join(b), title))

off = json.loads((R / "offline_eval.json").read_text()); ui = json.loads((R / "ui_smoke_test.json").read_text())
rows = off["rows"]
items = []
for r in rows:
    g = r["expected_primary_doc"]; k = r["retrieved_ids"].index(g) + 1 if g in r["retrieved_ids"] else 0
    ann = (f"rank {k}" if k else "off-corpus: returned unrelated text") + (" · answer OK" if r["answer_matches_question"] else " · WRONG answer")
    items.append((r["query"][:55], (5 - k) if k else 0.02, TEAL if r["answer_matches_question"] else RED, ann))
hbar("chart_per_query_retrieval_and_answer", items,
     "Offline eval of app.py: rank of expected source doc (bar length) and answer correctness\nteal = answer matches question · red = wrong canned answer / irrelevant text", 4.0, label_w=360)

st_ = off["summary"]["rerank_score_by_rank_over_50_runs"]; ks = list(st_)
vbar("chart_relevance_score_by_rank", [k.replace("_", " ") for k in ks], [("mean", [st_[k]["mean"] for k in ks], TEAL)],
     "Displayed 'Relevance' by result rank, same query run 50 times\nscore = max(0.35, 0.94 - 0.09*rank)*0.98 + uniform noise (whisker = min-max)",
     errs=[(st_[k]["min"], st_[k]["max"]) for k in ks], ylab="relevance shown in UI", w=600)

lat = [r["latency_ms"] for r in rows]
vbar("chart_latency_per_query", [f"Q{i+1}" for i in range(len(rows))], [("ms", lat, TEAL)],
     f"Offline in-process latency per query (retrieve + generate), median {off['summary']['latency_ms_median']} ms\n"
     f"UI browser round-trip ~{sorted(q['browser_roundtrip_ms'] for q in ui['queries'])[len(ui['queries'])//2]} ms; app's own 'Answered in' caption = 0 ms",
     ymax=round(max(lat) * 1.25, 2), fmt="{:.2f}", ylab="ms", w=820)

st = types.ModuleType("streamlit"); st.set_page_config = lambda **k: None; st.markdown = lambda *a, **k: None
sys.modules["streamlit"] = st; ns = {}
exec((ROOT / "app.py").read_text().split("for k, v in [('auth', False)")[0], ns)
C = ns["CORPUS"]
for key, nm in [("source", "source"), ("topic", "topic")]:
    c = Counter(d[key] for d in C).most_common()
    hbar(f"chart_corpus_by_{nm}", [(k, v, TEAL, str(v)) for k, v in c], f"FinRAG India corpus: documents per {nm} ({len(c)} distinct, {len(C)} docs)",
         max(v for _, v in c), label_w=180, w=620, bar_h=12, gap=3)

abl = [("Dense only", .72, .77, .69, .67, .62), ("Sparse BM25 only", .65, .72, .65, .61, .56),
       ("Hybrid RRF", .81, .84, .75, .74, .69), ("Hybrid + re-rank", .87, .88, .81, .77, .72), ("FinRAG full", .89, .91, .84, .80, .75)]
mets = ["Faithfulness", "Answer relevancy", "Context recall", "NDCG@10", "MRR"]
vbar("chart_reported_ablation_not_reproduced", [a[0] for a in abl], [(m, [a[j+1] for a in abl], PAL[j]) for j, m in enumerate(mets)],
     "Ablation values as reported in the dissertation / hardcoded in the app's Evaluation tab\nNOT re-measured: the shipped app contains no RAGAS, embedding or LLM code",
     ymin=0.5, ymax=1.0, w=820)
for f in sorted(IMG.glob("*.svg")): print(f.name, f.stat().st_size)
