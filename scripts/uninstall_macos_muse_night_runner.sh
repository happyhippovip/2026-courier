#!/bin/bash
set -u

LABEL="com.couriersymphony.dev.muse-night"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This uninstaller is for macOS only." >&2
  exit 64
fi

launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"

echo "Removed launchd job: $LABEL"
echo "State/logs preserved at: $HOME/.courier/dev-night"
