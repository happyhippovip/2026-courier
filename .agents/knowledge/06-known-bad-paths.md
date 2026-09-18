# HISTORICAL SNAPSHOT — canonical queue is `ops/ai/DEFERRED_LEDGER_QUEUE.yaml`

# Known Bad Paths

BAD_PATH=Replayed Evidence / Duplicate Execution
EXPECTED_FAIL_CLOSED_BEHAVIOR=Idempotent 409 rejection and AMBIGUOUS_CRASH markers.
TEST=tests/test_windows_runtime_torture.py

BAD_PATH=Wrong Runtime SHA
EXPECTED_FAIL_CLOSED_BEHAVIOR=Server rejects worker registration with HTTP 426 Upgrade Required.
TEST=Source Code Inspection (`server/app.py:register_worker`)

BAD_PATH=Global WAITING_PROVIDER blockage
EXPECTED_FAIL_CLOSED_BEHAVIOR=Server unbinds the task (`current_task = None`) allowing the worker to immediately pull independent READY tasks.
TEST=Source Code Inspection (`server/app.py:result`)
