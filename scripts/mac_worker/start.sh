#!/bin/bash
set -euo pipefail
LABEL="com.courier.mac_worker"
if ! command -v launchctl >/dev/null 2>&1; then
  echo "Error: launchctl not found." >&2
  exit 1
fi
if ! launchctl list "$LABEL" >/dev/null 2>&1; then
  echo "Error: Service $LABEL is not loaded in launchctl. Run install.sh first." >&2
  exit 1
fi
launchctl start "$LABEL"
echo "Sent start signal to $LABEL."
