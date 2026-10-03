"""Headless UI smoke test for FinRAG India (Streamlit) using Playwright.

Starts from a running app at http://127.0.0.1:8501, logs in with a demo user,
asks sample questions, and records what the UI actually displayed.
"""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8501"
OUT = Path(__file__).resolve().parent.parent / "results"
IMG = OUT / "images"
IMG.mkdir(parents=True, exist_ok=True)

QUERIES = [
    "What is the current RBI repo rate?",                      # typed (also a sample question)
    "How did Indian equity markets perform in FY 2024-25?",    # typed (also a sample question)
    "What are the new income tax slabs in Budget 2025-26?",    # typed (also a sample question)
    "What is India's renewable energy capacity?",              # typed, in QA bank (not a button)
    "How much gold did India import and what drove prices?",   # typed, NOT in QA bank
    "SAMPLE:What is happening with the Indian rupee?",         # clicked via sample button
]

def wait_idle(page, t=1.5):
    # wait until Streamlit is not running a script
    page.wait_for_timeout(400)
    try:
        page.wait_for_selector("[data-testid='stStatusWidget']", state="detached", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(int(t * 1000))

def main():
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(URL); page.wait_for_selector("text=FinRAG India", timeout=30000); wait_idle(page)
        page.screenshot(path=str(IMG / "01_login.png"), full_page=True)

        # wrong password check
        page.get_by_role("textbox", name="Username").fill("demo")
        page.get_by_role("textbox", name="Password").fill("wrong")
        page.get_by_role("button", name="Sign in").click(); wait_idle(page)
        bad_login_error = page.locator("text=Invalid username or password").count() > 0

        page.get_by_role("textbox", name="Password").fill("demo123")
        page.get_by_role("button", name="Sign in").click()
        page.wait_for_selector("text=Ask about Indian markets", timeout=20000); wait_idle(page)
        page.screenshot(path=str(IMG / "02_ask_home.png"), full_page=True)

        for i, q in enumerate(QUERIES, 1):
            if q.startswith("SAMPLE:"):
                q = q[7:]
                page.get_by_role("button", name=q).click(); wait_idle(page, 1)
            else:
                box = page.get_by_label("Your question")
                box.fill(q); box.press("Enter"); wait_idle(page, 1)
            t0 = time.time()
            page.get_by_role("button", name="Ask", exact=True).click()
            page.wait_for_selector("text=Answered in", timeout=30000); wait_idle(page, 1)
            ui_ms = int((time.time() - t0) * 1000)
            answer = page.locator(".ans-box").inner_text()
            caption = page.locator("text=Answered in").first.inner_text()
            exp = page.locator("[data-testid='stExpander']")
            titles = [exp.nth(k).locator("summary").inner_text().strip() for k in range(exp.count())]
            if exp.count():
                exp.nth(0).locator("summary").click(); page.wait_for_timeout(600)
            rel = [float(x) for x in re.findall(r"Relevance: ([0-9.]+)", page.inner_text("body"))]
            page.screenshot(path=str(IMG / f"03_query_{i}.png"), full_page=True)
            m = re.search(r"Answered in (\d+) ms\s*\|\s*(\d+) sources\s*\|\s*(-?\d+) queries remaining", caption)
            rows.append({"query": q, "input": "sample button" if i == len(QUERIES) else "typed", "answer": answer, "sources": titles,
                         "first_source_relevance_shown": rel[0] if rel else None,
                         "app_reported_ms": int(m.group(1)) if m else None,
                         "n_sources": int(m.group(2)) if m else len(titles),
                         "queries_remaining_shown": int(m.group(3)) if m else None,
                         "browser_roundtrip_ms": ui_ms, "caption": caption})
            page.get_by_role("button", name="Clear").click(); wait_idle(page, 1)

        sb = page.locator("[data-testid='stSidebar']")
        sb.get_by_text("Browse documents").click(); wait_idle(page)
        page.screenshot(path=str(IMG / "04_browse_documents.png"))
        sb.get_by_text("System details").click(); wait_idle(page)
        page.screenshot(path=str(IMG / "05_system_pipeline.png"), full_page=True)
        page.get_by_role("tab", name="Data sources").click(); wait_idle(page)
        page.screenshot(path=str(IMG / "06_system_data_sources.png"), full_page=True)
        page.get_by_role("tab", name="Evaluation").click(); wait_idle(page)
        page.screenshot(path=str(IMG / "07_system_evaluation.png"), full_page=True)
        sb.get_by_text("Usage stats").click(); wait_idle(page)
        usage_text = page.inner_text("[data-testid='stMain']") if page.locator("[data-testid='stMain']").count() else page.inner_text("body")
        page.screenshot(path=str(IMG / "08_usage_stats.png"), full_page=True)
        b.close()
    out = {"bad_login_rejected": bad_login_error, "queries": rows, "usage_page_text": usage_text}
    (OUT / "ui_smoke_test.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False)[:6000])

if __name__ == "__main__":
    main()
