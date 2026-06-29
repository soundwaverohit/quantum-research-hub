#!/usr/bin/env bash
# Reset the dev database (DROP + recreate all tables) and re-seed demo data.
# Destructive: clears papers/ideas/experiments/events. Asks for confirmation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"

read -r -p "This will DROP all tables in the dev DB. Continue? [y/N] " ans
case "$ans" in
  y|Y|yes|YES) ;;
  *) echo "Aborted."; exit 1 ;;
esac

$PYTHON -m researcher_mcp.storage.db reset --yes
echo "Re-seeding demo data..."
$PYTHON scripts/seed_demo.py --keep
echo "Done."
