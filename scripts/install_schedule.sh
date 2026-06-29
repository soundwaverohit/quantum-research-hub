#!/usr/bin/env bash
# Install a macOS launchd agent that runs the daily research loop every morning.
# Usage:  scripts/install_schedule.sh [profile] [HH] [MM]
#   profile: low (default) | medium | high     time: default 07:30
# Re-run any time to update; see scripts/uninstall_schedule.sh to remove.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$(command -v python3)"
PROFILE="${1:-low}"
HOUR="${2:-7}"
MIN="${3:-30}"
LABEL="com.quantumresearchhub.daily"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
uid="$(id -u)"
# Logs go OUTSIDE the repo: ~/Desktop is a macOS TCC-protected location and a
# background launchd agent can't open files there (spawn fails with EX_CONFIG).
LOGDIR="$HOME/Library/Logs/QuantumResearchHub"

mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR" "$ROOT/data/logs"

cat > "$DEST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>-m</string><string>orchestrator.daily_run</string>
    <string>--profile</string><string>$PROFILE</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$(dirname "$PY"):/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
  <key>StandardOutPath</key><string>$LOGDIR/daily.out.log</string>
  <key>StandardErrorPath</key><string>$LOGDIR/daily.err.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLIST

# Reload (modern bootstrap, fall back to legacy load).
launchctl bootout "gui/$uid/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$DEST" 2>/dev/null || launchctl load -w "$DEST"

printf 'Installed %s — profile=%s, daily at %02d:%02d\n' "$LABEL" "$PROFILE" "$HOUR" "$MIN"
echo "Plist: $DEST"
if launchctl print "gui/$uid/$LABEL" >/dev/null 2>&1 || launchctl list | grep -q "$LABEL"; then
  echo "Status: loaded ✓   (run now: launchctl kickstart gui/$uid/$LABEL)"
else
  echo "Status: WARN — not confirmed loaded; check 'launchctl list | grep $LABEL'"
fi
