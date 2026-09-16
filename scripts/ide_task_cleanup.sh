#!/bin/bash
# IDE Task Cleanup Watchdog
# Kills background test scripts (run_*, test_*) that have been running for > 15 minutes (900 seconds)

echo "$(date): Running IDE Task Cleanup..."

# Find python scripts matching run_*.py or test_*.py that have been running for > 900 seconds
PIDS=$(ps -eo pid,etimes,command | awk '{if ($2 > 900 && $3 ~ /python/ && ($4 ~ /run_/ || $4 ~ /test_/)) print $1}')

if [ -n "$PIDS" ]; then
    echo "Found stale IDE tasks. Killing PIDs: $PIDS"
    for pid in $PIDS; do
        kill -9 $pid 2>/dev/null
    done
else
    echo "No stale IDE tasks found."
fi
