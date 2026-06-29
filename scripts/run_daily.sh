#!/usr/bin/env bash
# Run the daily research orchestrator. Pass-through args, e.g.:
#   scripts/run_daily.sh --profile medium --lookback-days 3
# Override the interpreter with: PYTHON="uv run python" scripts/run_daily.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
exec $PYTHON -m orchestrator.daily_run "${@:---profile low}"
