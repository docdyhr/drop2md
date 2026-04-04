#!/usr/bin/env bash
# uninstall.sh — Remove drop2md launchd service
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.thomasdyhr.drop2md.plist"

if [[ -f "$PLIST" ]]; then
  echo "Unloading launchd service..."
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Service removed: $PLIST"
else
  echo "No launchd service found at $PLIST"
fi

echo "Done. The .venv and output files are not removed."
echo "To fully remove: rm -rf .venv output/"
