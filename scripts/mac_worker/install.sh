#!/bin/bash
set -euo pipefail
# Resolve paths from this script's location so it works from any cwd
# (setup_local_autonomy.sh calls it from the repository root).
HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$(cd "$HERE/../.." && pwd)"

# Discover Python binary dynamically if not specified
PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
  if [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
  elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
  elif [ -x "/usr/bin/python3" ]; then
    PYTHON_BIN="/usr/bin/python3"
  else
    PYTHON_BIN="/usr/local/bin/python3"
  fi
fi

LABEL="com.courier.mac_worker"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${PLIST_DIR}/${LABEL}.plist"

mkdir -p "$PLIST_DIR" "$HERE/logs"

sed -e "s|TARGET_DIR|$TARGET_DIR|g" \
    -e "s|/usr/local/bin/python3|$PYTHON_BIN|g" \
    "$HERE/com.courier.mac_worker.plist" > "$PLIST_PATH"

if ! command -v launchctl >/dev/null 2>&1; then
  echo "Warning: launchctl not found; plist written to $PLIST_PATH but service not loaded." >&2
  exit 0
fi

# Unload older registration if present
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load service
if ! launchctl load "$PLIST_PATH"; then
  echo "Error: launchctl load failed for $PLIST_PATH" >&2
  exit 1
fi

# Verify registration truthful proof in launchctl without grep
if ! launchctl list "$LABEL" >/dev/null 2>&1; then
  echo "Error: Service $LABEL was not registered in launchctl after load." >&2
  exit 1
fi

echo "Mac worker installed to launchd and verified: $LABEL"
