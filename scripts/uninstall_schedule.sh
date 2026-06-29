#!/usr/bin/env bash
# Remove the Quantum Research Hub launchd daily schedule.
set -euo pipefail
LABEL="com.quantumresearchhub.daily"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
uid="$(id -u)"

launchctl bootout "gui/$uid/$LABEL" 2>/dev/null || launchctl unload -w "$DEST" 2>/dev/null || true
rm -f "$DEST"
echo "Removed $LABEL and its plist. The daily run will no longer fire automatically."
