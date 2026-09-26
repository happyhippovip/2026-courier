#!/bin/bash
set -e
# Resolve paths from this script's location so it works from any cwd
# (setup_local_autonomy.sh calls it from the repository root).
HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$(cd "$HERE/../.." && pwd)"
mkdir -p ~/Library/LaunchAgents "$HERE/logs"
sed -e "s|TARGET_DIR|$TARGET_DIR|g" -e "s|PYTHON_BIN|$(which python3)|g" -e "s|USER_HOME|$HOME|g" "$HERE/com.courier.mac_worker.plist" > ~/Library/LaunchAgents/com.courier.mac_worker.plist
launchctl unload ~/Library/LaunchAgents/com.courier.mac_worker.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist
echo "Mac worker installed to launchd and started."
