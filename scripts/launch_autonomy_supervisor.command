#!/bin/bash
# 2026 Autonomy Supervisor OS Launcher
# Starts and keeps the Autonomy Supervisor running with bounded backoff.

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$DIR:$PYTHONPATH"

echo "=========================================================="
echo "🚀 STARTING 2026 AUTONOMY SUPERVISOR (DAEMON WATCHDOG)"
echo "=========================================================="

while true; do
    echo "[SUPERVISOR_LAUNCHER] $(date) - Invoking Autonomy Supervisor..."
    python3 "$DIR/scripts/autonomy_supervisor.py" || {
        EXIT_CODE=$?
        echo "[SUPERVISOR_LAUNCHER] $(date) - Supervisor exited with code $EXIT_CODE. Backoff 5s..."
        sleep 5
    }
    sleep 2
done
