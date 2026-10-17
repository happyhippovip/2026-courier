#!/bin/bash
# RUN_2 Preparation Script (Restart/Crash Recovery Proof)
# Designed for Mac Exact Binding Execution

set -e

echo "== N2: RUN1_TO_RUN2_GATE Validation =="
if [ ! -f "artifacts/RUN_1_SUCCESS" ]; then
    echo "ERROR: RUN_2 aborted. RUN_1 did not complete successfully (missing artifacts/RUN_1_SUCCESS)."
    exit 1
fi

echo "== RUN_2: Simulating Unclean Restart =="
# Deliberately kill the server process abruptly if it exists to test recovery
if [ -f logs/server.pid ]; then
    OLD_PID=$(cat logs/server.pid)
    echo "Killing old server PID: $OLD_PID"
    kill -9 $OLD_PID 2>/dev/null || true
    rm logs/server.pid
fi

echo "== RUN_2: Checking Port Conflicts =="
# Wait to ensure port is freed by OS
sleep 2

if lsof -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: Port 8080 is still in use after kill. Port-conflict recovery failed."
    exit 1
fi

echo "== RUN_2: Command Bindings =="
echo "Restarting Server..."
# Reuse the exact same db file to prove durability
python3 -m server.app --port=8080 --db=ledger_run1.db > logs/server_run2.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > logs/server.pid

sleep 2

echo "Starting Worker..."
python3 -m scripts.integration_contract > logs/worker_run2.log 2>&1 &
WORKER_PID=$!

echo "Starting Verifier for Task B..."
# Task B must run correctly if Task A was correctly reconciled in RUN_1
python3 -m scripts.courier_verifier --target=B > logs/verifier_run2.log 2>&1

echo "RUN_2 initiated. Verify that Task A was NOT re-dispatched and Task B was dispatched correctly."
