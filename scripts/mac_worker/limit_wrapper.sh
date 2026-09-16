#!/bin/bash
# Wrapper to run commands with reduced priority on macOS.
# Propagates termination to the child process group.

set -o monitor  # Enable job control so child gets its own pgrp

if [ $# -eq 0 ]; then
    echo "Usage: $0 <command> [args...]"
    exit 1
fi

CHILD_PID=""
CLEANED=0

cleanup() {
    if [ "$CLEANED" -eq 1 ]; then return; fi
    CLEANED=1
    if [ -n "$CHILD_PID" ]; then
        # Send TERM to the child's entire process group
        kill -TERM -- -"$CHILD_PID" 2>/dev/null
        # Bounded wait for graceful shutdown
        local i=0
        while [ $i -lt 10 ]; do
            kill -0 "$CHILD_PID" 2>/dev/null || break
            sleep 0.5
            i=$((i + 1))
        done
        # Hard kill if still alive
        kill -0 "$CHILD_PID" 2>/dev/null && kill -KILL -- -"$CHILD_PID" 2>/dev/null
        wait "$CHILD_PID" 2>/dev/null
    fi
}

trap cleanup TERM INT

"$@" &
CHILD_PID=$!

# Lower CPU priority (niceness)
renice 10 -p $CHILD_PID >/dev/null 2>&1

# Lower I/O and scheduling priority if taskpolicy is available (macOS specific)
if command -v taskpolicy >/dev/null 2>&1; then
    taskpolicy -b -p $CHILD_PID >/dev/null 2>&1
fi

wait $CHILD_PID
EXIT_CODE=$?

# Ensure cleanup ran (covers normal exit too)
cleanup

trap - TERM INT
exit $EXIT_CODE
