"""Build charts + metrics.json from results/offline_eval.json and results/ui_smoke_test.json."""
import json, sys, types
from collections import Counter
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["svg.fonttype"] = "none"; plt.rcParams["svg.hashsalt"] = "finrag"

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"; IMG = R / "images"
off = json.loads((R / "offline_eval.json").read_text())
ui = json.loads((R / "ui_smoke_test.json").read_text())

st = types.ModuleType("streamlit"); st.set_page_config = lambda **k: None; st.markdown = lambda *a, **k: None
sys.modules["streamlit"] = st; ns = {}
exec((ROOT / "app.py").read_text().split("for k, v in [('auth', False)")[0], ns)
CORPUS = ns["CORPUS"]

def save(fig, name):
    fig.tight_layout(); fig.savefig(IMG / f"{name}.png", dpi=130); plt.close(fig)

TEAL, RED, GREY = "#0f766e", "#dc2626", "#94a3b8"

# 1. Per-query: rank of expected doc + answer correctness
rows = off["rows"]
fig, ax = plt.subplots(figsize=(11, 6.5))
labels = [r["query"][:52] + ("…" if len(r["query"]) > 52 else "") for r in rows]
rank = [(r["retrieved_ids"].index(r["expected_primary_doc"]) + 1) if r["expected_primary_doc"] in r["retrieved_ids"] else 0 for r in rows]
y = range(len(rows))
ax.barh(y, [5 - k if k else 0 for k in rank], color=[TEAL if r["answer_matches_question"] else RED for r in rows])
for i, (k, r) in enumerate(zip(rank, rows)):
    ax.text((5 - k if k else 0) + 0.05, i, f"rank {k}" if k else ("off-corpus query: app returned unrelated text instead of no-result" if not r["expected_primary_doc"] else "not retrieved"), va="center", fontsize=8)
ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=8); ax.invert_yaxis()
ax.set_xticks([0, 1, 2, 3, 4]); ax.set_xticklabels(["", "rank 4", "rank 3", "rank 2", "rank 1"])
ax.set_title("Offline eval of shipped app.py: rank of expected source doc (bar) and answer correctness (colour)\n"
             "teal = answer matches the question, red = wrong canned answer / irrelevant text", fontsize=10)
save(fig, "chart_per_query_retrieval_and_answer")

# 2. Displayed 'Relevance' score vs rank (shows it is rank-derived)
stab = off["summary"]["rerank_score_by_rank_over_50_runs"]
fig, ax = plt.subplots(figsize=(7, 4))
ks = list(stab); means = [stab[k]["mean"] for k in ks]
err = [[stab[k]["mean"] - stab[k]["min"] for k in ks], [stab[k]["max"] - stab[k]["mean"] for k in ks]]
ax.bar([k.replace("_", " ") for k in ks], means, yerr=err, capsize=6, color=TEAL)
for i, m in enumerate(means): ax.text(i, m + 0.02, f"{m:.3f}", ha="center", fontsize=9)
ax.set_ylim(0, 1.05); ax.set_ylabel("'Relevance' shown in UI (rerank field)")
ax.set_title("Displayed relevance by result rank, 50 runs of the same query\n(score = max(0.35, 0.94 - 0.09*rank)*0.98 ± uniform noise)", fontsize=10)
save(fig, "chart_relevance_score_by_rank")

# 3. Latency
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(range(len(rows)), [r["latency_ms"] for r in rows], color=TEAL)
ax.set_xticks(range(len(rows))); ax.set_xticklabels([f"Q{i+1}" for i in range(len(rows))], fontsize=8)
ax.set_ylabel("ms (retrieve + generate)")
ax.set_title(f"Offline in-process latency per query (median {off['summary']['latency_ms_median']} ms)\n"
             f"UI browser round-trip median {sorted(q['browser_roundtrip_ms'] for q in ui['queries'])[len(ui['queries'])//2]} ms; app's own 'Answered in' caption = 0 ms", fontsize=10)
save(fig, "chart_latency_per_query")

# 4. Corpus composition
fig, axs = plt.subplots(1, 2, figsize=(13, 6))
for ax, key, title in [(axs[0], "source", "Documents per source"), (axs[1], "topic", "Documents per topic")]:
    c = Counter(d[key] for d in CORPUS).most_common()
    ax.barh([k for k, _ in c], [v for _, v in c], color=TEAL); ax.invert_yaxis()
    ax.tick_params(axis="y", labelsize=8); ax.set_title(f"{title} ({len(c)} distinct)")
fig.suptitle(f"FinRAG India corpus: {len(CORPUS)} documents (embedded in app.py)")
save(fig, "chart_corpus_composition")

# 5. Report ablation numbers (hardcoded in app; NOT reproduced here)
abl = [("Dense only", .72, .77, .69, .67, .62), ("Sparse BM25 only", .65, .72, .65, .61, .56),
       ("Hybrid RRF", .81, .84, .75, .74, .69), ("Hybrid + re-rank", .87, .88, .81, .77, .72), ("FinRAG full", .89, .91, .84, .80, .75)]
mets = ["Faithfulness", "Answer relevancy", "Context recall", "NDCG@10", "MRR"]
fig, ax = plt.subplots(figsize=(10, 4.5)); w = 0.16
for j, m in enumerate(mets):
    ax.bar([i + j * w for i in range(5)], [a[j + 1] for a in abl], w, label=m)
ax.set_xticks([i + 2 * w for i in range(5)]); ax.set_xticklabels([a[0] for a in abl]); ax.set_ylim(0.5, 1)
ax.legend(fontsize=8, ncol=5, loc="upper left")
ax.set_title("Ablation values as reported in the dissertation / hardcoded in the app's Evaluation tab\n(NOT re-measured in this run: the shipped app contains no RAGAS/embedding/LLM code)", fontsize=10)
save(fig, "chart_reported_ablation_not_reproduced")

s = off["summary"]
bank = [r for r in rows if r["in_qa_bank"]]
metrics = {
    "run_timestamp_ist": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M IST"),
    "environment": {"streamlit": __import__("importlib.metadata").metadata.version("streamlit"), "python": sys.version.split()[0],
                    "browser": "Playwright headless Chromium", "external_api_keys_required": False},
    "ui_smoke_test": {
        "login_user": "demo", "bad_password_rejected": ui["bad_login_rejected"],
        "queries_asked": len(ui["queries"]),
        "answers_correct_for_question": None,  # filled below
        "app_reported_latency_ms": [q["app_reported_ms"] for q in ui["queries"]],
        "browser_roundtrip_ms": [q["browser_roundtrip_ms"] for q in ui["queries"]],
        "quota_after_run": "19 of 25 remaining, 6 total (Usage page)",
        "remaining_caption_under_answer_off_by_one": True,
    },
    "offline_eval": s,
    "qa_bank_questions_answered_correctly": f"{sum(r['answer_matches_question'] for r in bank)}/{len(bank)}",
    "free_form_probes_answered_correctly": f"{sum(r['answer_matches_question'] for r in rows if not r['in_qa_bank'])}/{sum(1 for r in rows if not r['in_qa_bank'])}",
    "reported_ablation_from_dissertation_not_reproduced": {a[0]: dict(zip(mets, a[1:])) for a in abl},
}
own = {r["query"]: r["answer_matches_question"] for r in rows}
metrics["ui_smoke_test"]["answers_correct_for_question"] = f"{sum(bool(own.get(q['query'])) for q in ui['queries'])}/{len(ui['queries'])}"
(R / "metrics.json").write_text(json.dumps(metrics, indent=2))
print(json.dumps(metrics, indent=2)[:2500])
