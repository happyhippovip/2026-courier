#!/bin/bash
# Wrapper to run commands with reduced priority on macOS to prevent system freezes.

if [ $# -eq 0 ]; then
    echo "Usage: $0 <command> [args...]"
    exit 1
fi

# Run the command in the background
"$@" &
PID=$!

# Lower CPU priority (niceness)
renice 10 -p $PID >/dev/null 2>&1

# Lower I/O and scheduling priority if taskpolicy is available (macOS specific)
if command -v taskpolicy >/dev/null 2>&1; then
    taskpolicy -b -p $PID >/dev/null 2>&1
fi

# Wait for the process to finish
wait $PID
exit $?
