#!/usr/bin/env bash
# Bootstrap the Quantum Research Hub: install deps, create .env, init + seed DB.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Installing dependencies"
if command -v uv >/dev/null 2>&1; then
  uv sync || { echo "uv sync failed; falling back to pip"; python3 -m pip install -e ".[dev]"; }
  PY="uv run python"
else
  python3 -m pip install -e ".[dev]"
  PY="python3"
fi

echo "==> Creating .env (if missing)"
[ -f .env ] || cp .env.example .env

echo "==> Initializing database"
$PY -m researcher_mcp.storage.db init

echo "==> Seeding demo data"
$PY scripts/seed_demo.py

cat <<EOF

Bootstrap complete. Next:
  $PY -m orchestrator.daily_run --profile low       # daily research run
  ${PY/python/streamlit} run apps/dashboard/Home.py  # dashboard (or: streamlit run apps/dashboard/Home.py)
  $PY -m pytest                                      # tests
EOF
