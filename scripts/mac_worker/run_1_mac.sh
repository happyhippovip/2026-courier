#!/bin/bash
# RUN_1 Preparation Script (Candidate-Independent)
# Designed for Mac Exact Binding Execution

set -e

echo "== RUN_1: Isolated Workspace Layout =="
mkdir -p logs artifacts/run1
rm -f ledger_run1.db
touch ledger_run1.db

echo "== RUN_1: Port & Process Isolation =="
if lsof -i :8080 | grep -q "LISTEN"; then
    echo "ERROR: Port 8080 is already in use. Run aborted."
    exit 1
fi

echo "== RUN_1: Command Bindings =="
echo "Starting Server..."
python3 -m server.app --port=8080 --db=ledger_run1.db > logs/server_run1.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > logs/server.pid

sleep 2

echo "Starting Worker..."
python3 -m scripts.integration_contract > logs/worker_run1.log 2>&1 &
WORKER_PID=$!

echo "Starting Verifier for Task A..."
python3 -m scripts.courier_verifier --target=A > logs/verifier_run1.log 2>&1

if [ $? -eq 0 ]; then
    echo "RUN_1 completed successfully. Authorizing RUN_2."
    touch artifacts/RUN_1_SUCCESS
else
    echo "ERROR: RUN_1 verification failed."
    exit 1
fi

echo "RUN_1 initiated. Human relay count should be 0 from this point."
echo "Wait for Task A exactly once, then run run_2_mac.sh"
