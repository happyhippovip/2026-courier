#!/bin/bash
cd /Users/user/Downloads/2026-courier
export PYTHONPATH=.

# Start the founder loop
python3 scripts/courier_founder_mode.py --goal "Create a file named events/reports/fault_test_999.txt containing exactly: HELLO" &
COURIER_PID=$!
echo "COURIER_PID=$COURIER_PID"

# Wait for the file to exist
while [ ! -f events/reports/fault_test_999.txt ]; do
    if ! kill -0 $COURIER_PID 2>/dev/null; then
        echo "Courier died before creating the file!"
        exit 1
    fi
    sleep 0.1
done

echo "File created! Killing courier ($COURIER_PID) immediately!"
kill -TERM $COURIER_PID
echo "Killed."
