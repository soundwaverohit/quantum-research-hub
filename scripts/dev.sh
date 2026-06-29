#!/usr/bin/env bash
# Dev convenience: init DB (if needed), seed demo data, then launch the dashboard.
# Override interpreter with PYTHON="uv run python".
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"

$PYTHON -m researcher_mcp.storage.db init
$PYTHON scripts/seed_demo.py --keep || $PYTHON scripts/seed_demo.py

# Zero-dependency dashboard (always runs). For the Streamlit version instead:
#   streamlit run apps/dashboard/Home.py
echo "==> Launching dashboard at http://127.0.0.1:8533"
exec $PYTHON -m apps.dashboard.server
