#!/bin/bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/com.courier.mac_worker.plist"

mkdir -p "$LAUNCH_AGENTS"
sed -e "s|TARGET_DIR|$TARGET_DIR|g" "$SCRIPT_DIR/com.courier.mac_worker.plist" > "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Mac worker installed to launchd and started."
