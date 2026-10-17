#!/bin/bash
set -euo pipefail
LABEL="com.courier.mac_worker"
if ! command -v launchctl >/dev/null 2>&1; then
  echo "Error: launchctl not found." >&2
  exit 1
fi
if ! launchctl list "$LABEL" >/dev/null 2>&1; then
  echo "Service $LABEL is already stopped or not loaded."
  exit 0
fi
launchctl stop "$LABEL"
echo "Sent stop signal to $LABEL."
