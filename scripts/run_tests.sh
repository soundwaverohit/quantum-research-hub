#!/usr/bin/env bash
# Run the test suite. Override interpreter with PYTHON="uv run python".
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
exec $PYTHON -m pytest "$@"
