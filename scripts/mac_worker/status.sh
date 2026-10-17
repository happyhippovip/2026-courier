#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$HERE/status.py" "$@"
fi
# Direct fallback if python3 is unavailable (zero grep)
LABEL="com.courier.mac_worker"
if launchctl list "$LABEL" >/dev/null 2>&1; then
  echo "Service $LABEL is loaded in launchctl."
  exit 0
else
  echo "Service $LABEL is not running or not loaded in launchctl." >&2
  exit 1
fi
