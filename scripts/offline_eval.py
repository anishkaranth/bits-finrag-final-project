"""Offline evaluation of the retrieval/answer logic that ships in app.py.

Executes only the non-UI part of app.py (corpus, QA bank, score_doc, retrieve,
generate) with a stub `streamlit` module, then measures what the code really does.
Nothing here calls an external API.
"""
import json, random, re, statistics, sys, time, types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "app.py").read_text()
core = src.split("for k, v in [('auth', False)")[0]
st = types.ModuleType("streamlit")
st.set_page_config = lambda **k: None
st.markdown = lambda *a, **k: None
sys.modules["streamlit"] = st
ns = {}
exec(compile(core, "app_core", "exec"), ns)
CORPUS, QA, retrieve, generate = ns["CORPUS"], ns["QA"], ns["retrieve"], ns["generate"]

def answer_owner(ans):
    for k, v in QA.items():
        if v["ans"] == ans:
            return k
    return None  # extractive fallback

# Extra probes, with the doc id a human would expect as the primary source.
PROBES = [
    ("How much gold did India import and what drove prices?", "IND035", None),
    ("What is the UPI transaction volume?", "IND007", None),
    ("How are microfinance loans performing?", "IND021", None),
    ("What did the CCI fine Meta and WhatsApp?", "IND056", None),
    ("Who won the cricket world cup?", None, None),
]

def gold_text(i):
    return next(d['text'] for d in CORPUS if d['id'] == i)

random.seed(0)
rows = []
cases = [(k, v["ids"][0], k) for k, v in QA.items()] + PROBES
for q, gold, expected_key in cases:
    t0 = time.perf_counter(); chunks = retrieve(q, top_k=4); ans = generate(q, chunks)
    ms = (time.perf_counter() - t0) * 1000
    ids = [c["id"] for c in chunks]
    owner = answer_owner(ans)
    rows.append({
        "query": q, "in_qa_bank": q in QA, "expected_primary_doc": gold,
        "retrieved_ids": ids, "rerank_scores": [c["rerank"] for c in chunks],
        "dense_scores": [c["dense"] for c in chunks], "sparse_scores": [c["sparse"] for c in chunks],
        "hit_at_1": (ids[:1] == [gold]) if gold else None,
        "hit_at_4": (gold in ids) if gold else None,
        "rr": (1 / (ids.index(gold) + 1) if gold in ids else 0.0) if gold else None,
        "answer_mode": "canned" if owner else ("no_result" if not chunks else "extractive"),
        "canned_answer_from": owner,
        # bank question: correct iff its own canned answer is returned.
        # free-form probe: correct iff no (wrong) canned answer and the expected doc's text is in the answer;
        # off-corpus probe: correct iff the app says nothing relevant was found.
        "answer_matches_question": (owner == expected_key) if expected_key else (
            (owner is None and gold_text(gold)[:80] in ans) if gold else (not chunks)),
        "latency_ms": round(ms, 3), "answer": ans,
    })

# Score stability: same query 50 times -> scores depend only on rank + noise.
stab = {}
for r in range(4):
    vals = [retrieve("What is the current RBI repo rate?")[r]["rerank"] for _ in range(50)]
    stab[f"rank_{r+1}"] = {"min": min(vals), "max": max(vals), "mean": round(statistics.mean(vals), 4)}

lat = [r["latency_ms"] for r in rows]
graded = [r for r in rows if r["expected_primary_doc"]]
summary = {
    "corpus_documents": len(CORPUS),
    "distinct_sources": len({d["source"] for d in CORPUS}),
    "distinct_topics": len({d["topic"] for d in CORPUS}),
    "qa_bank_size": len(QA),
    "queries_evaluated": len(rows),
    "graded_queries": len(graded),
    "hit_at_1": round(sum(r["hit_at_1"] for r in graded) / len(graded), 3),
    "hit_at_4": round(sum(r["hit_at_4"] for r in graded) / len(graded), 3),
    "mrr": round(sum(r["rr"] for r in graded) / len(graded), 3),
    "answers_matching_question": sum(bool(r["answer_matches_question"]) for r in rows),
    "latency_ms_median": round(statistics.median(lat), 3),
    "latency_ms_max": round(max(lat), 3),
    "rerank_score_by_rank_over_50_runs": stab,
}
out = {"summary": summary, "rows": rows}
(ROOT / "results" / "offline_eval.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(json.dumps(summary, indent=2))
for r in rows:
    print(f"{'OK ' if r['answer_matches_question'] else 'BAD'} hit1={r['hit_at_1']} mode={r['answer_mode']:<10} {r['query'][:55]:<55} -> {r['retrieved_ids']} canned_from={r['canned_answer_from']}")
