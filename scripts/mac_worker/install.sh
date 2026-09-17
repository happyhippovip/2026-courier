#!/bin/bash
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET_DIR=$(cd "$SCRIPT_DIR/../.." && pwd)
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/com.courier.mac_worker.plist"
PYTHON_BIN="$TARGET_DIR/venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN=$(command -v python3 || true)
fi
if [ -z "$PYTHON_BIN" ] || ! "$PYTHON_BIN" -c 'import flask, requests, psutil, keyring' >/dev/null 2>&1; then
    echo "Courier Python runtime dependencies are not installed; refusing to register a broken launchd worker." >&2
    exit 1
fi

mkdir -p "$LAUNCH_AGENTS"
sed -e "s|TARGET_DIR|$TARGET_DIR|g" -e "s|PYTHON_BIN|$PYTHON_BIN|g" "$SCRIPT_DIR/com.courier.mac_worker.plist" > "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Mac worker installed to launchd and started."
