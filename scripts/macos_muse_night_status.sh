#!/bin/bash
set -u

LABEL="com.couriersymphony.dev.muse-night"
STATE_DIR="${COURIER_NIGHT_STATE_DIR:-$HOME/.courier/dev-night}"

echo "=== launchd ==="
if command -v launchctl >/dev/null 2>&1; then
  launchctl print "gui/$UID/$LABEL" 2>/dev/null | sed -n '1,45p' || echo "not loaded"
else
  echo "launchctl unavailable"
fi

echo
echo "=== guard state ==="
if [ -f "$STATE_DIR/RESOURCE_PAUSE" ]; then
  echo "RESOURCE_PAUSE=YES"
  cat "$STATE_DIR/RESOURCE_PAUSE"
else
  echo "RESOURCE_PAUSE=NO"
fi

if [ -f "$STATE_DIR/BACKOFF_UNTIL" ]; then
  echo "BACKOFF_UNTIL=$(cat "$STATE_DIR/BACKOFF_UNTIL")"
else
  echo "BACKOFF_UNTIL=none"
fi

echo
echo "=== queue state tail ==="
if [ -f "$STATE_DIR/STATE.md" ]; then
  tail -n 50 "$STATE_DIR/STATE.md"
else
  echo "STATE.md not created yet"
fi

echo
echo "=== runner log tail ==="
if [ -f "$STATE_DIR/runner.log" ]; then
  tail -n 60 "$STATE_DIR/runner.log"
else
  echo "runner.log not created yet"
fi
