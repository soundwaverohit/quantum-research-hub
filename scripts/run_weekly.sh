#!/usr/bin/env bash
# Write the weekly research report. Pass-through args, e.g.:
#   scripts/run_weekly.sh --profile medium --week-start 2026-06-01
# Override the interpreter with: PYTHON="uv run python" scripts/run_weekly.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
exec $PYTHON -m orchestrator.scheduler weekly "${@:---profile low}"
