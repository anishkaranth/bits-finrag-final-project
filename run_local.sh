#!/usr/bin/env bash
# Run FinRAG India locally (no tunnel). Open http://localhost:8501
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install -q streamlit pandas
.venv/bin/streamlit run app.py --server.port 8501 --server.headless true \
  --theme.base light --theme.primaryColor '#0f766e' --browser.gatherUsageStats false
