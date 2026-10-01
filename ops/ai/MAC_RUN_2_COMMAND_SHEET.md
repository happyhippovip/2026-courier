# RUN_2 Command Sheet (Mac Restart Operator)

This command sheet is designed for the Mac Physical Runner to execute `RUN_2`, proving that restart mechanisms correctly recover state without duplicating efforts.

## Prerequisites
1. `RUN_1` must have completed successfully.
2. `ledger_run1.db` must exist and contain the `RECONCILED` state of Task A.

## Step 1: Execute RUN_2
```bash
bash scripts/mac_worker/run_2_mac.sh
```
This script explicitly simulates a crash by `kill -9` on any existing server, waits to ensure the port clears, then restarts the server and binds Task B.

## Step 2: Verify Restart State
Examine `logs/server_run2.log` and `logs/worker_run2.log`.
- **CRITICAL PROOF**: Task A MUST NOT be dispatched again.
- **SUCCESS PROOF**: Task B MUST be dispatched because Task A was already RECONCILED.

## Step 3: Verify B's State
Ensure `logs/verifier_run2.log` confirms Task B is successfully verified.

## Step 4: Final Output
Save `ledger_run1.db` to `artifacts/run2/ledger_run2.db` to preserve the end state.
