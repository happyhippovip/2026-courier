# FINAL CONCURRENCY HANDOFF

## 1. Concurrency Audit Findings
- **Worker Claim Concurrency**: `@serialize_state_mutation` (backed by a `threading.RLock`) safely protects all mutable API endpoints in `server/app.py`. There are no unprotected concurrent writes. Thus, two workers cannot be assigned the same task from a race condition inside `claim_task`.
- **Result Idempotency**: `task_result` properly detects duplicated results for a task that is already `RECONCILED` or `RESULT_RECEIVED` and returns an `ACK_DUPLICATE` (200 OK) response.
- **Verifier Race**: If multiple verifiers submit results simultaneously, the second one will receive a `403 alias attack on replay rejected`. This gracefully fails the concurrent submission and prevents it from mutating the validated verification metadata. 

## 2. Claim Idempotency Issue Fixed
- **The Defect**: If a worker called `/tasks/claim` and the server transitioned the task to `DISPATCHED` and updated `worker["current_task"]`, but the worker dropped the network payload, the worker would fall back to polling. On its next poll, the server saw that the worker was busy with a `DISPATCHED` task, and returned a hard `WORKER_BUSY` (with no task payload). The worker would remain completely stuck, and the task would be marooned in the `DISPATCHED` state permanently because the worker didn't know what task to execute. 
- **The Fix**: Made `/tasks/claim` fully idempotent. If the server detects the worker is busy with a `DISPATCHED` task, it now resends the assigned task payload instead of blocking it with `WORKER_BUSY`. This guarantees exactly-once processing even across severe network disruptions.
- **Verification**: Updated `tests/test_server_integration_contract.py` to assert correct concurrent state handling using multiple distinct worker IDs, which successfully passes.

## 3. Next Steps
Move to the next prioritized task in the autonomous queue: **COURIER — P0 MUTATION TRACE / FORENSIK** (Read-only forensic analysis to determine what modifies Checkout/Ledger/Runtime on the Mac).

