# OBSERVABILITY / TIMESTAMPS

## Status: VERIFIED (GREEN)

### 1. `dispatched_at` is securely server-generated
CASE= When a worker claims a task, the server records the exact dispatch time.
SOURCE_PATH= server/app.py (claim_task)
MECHANISM= `next_task["dispatched_at"] = time.time()` is set before returning the task to the worker. This cannot be forged by the worker.
EXPECTED= Server-controlled `dispatched_at`.
ACTUAL= `dispatched_at` is server-controlled.
PASS|DEFECT= PASS

### 2. `execution_start_at` / `execution_end_at` required from worker
CASE= The worker must report when it actually started and ended execution.
SOURCE_PATH= scripts/integration_contract.py (validate_durable_result)
MECHANISM= Both fields are in the `required` set. `validate_durable_result` ensures they are present and are numbers (`int` or `float`).
EXPECTED= Rejects results lacking execution timing.
ACTUAL= Rejects results lacking execution timing.
PASS|DEFECT= PASS

### 3. `result_received_at` is securely server-generated
CASE= Server captures when the network upload finished and result is accepted.
SOURCE_PATH= server/app.py (task_result)
MECHANISM= `task["result_received_at"] = time.time()` is set when persisting the `RESULT_RECEIVED` state.
EXPECTED= Server-controlled receive time.
ACTUAL= Server-controlled receive time.
PASS|DEFECT= PASS

### 4. `reconciled_at` is securely server-generated
CASE= Server captures when the verifier emitted a PASS verdict.
SOURCE_PATH= server/app.py (verify_task_result)
MECHANISM= `task["reconciled_at"] = time.time()` is set when persisting the `RECONCILED` state.
EXPECTED= Server-controlled reconcile time.
ACTUAL= Server-controlled reconcile time.
PASS|DEFECT= PASS

### 5. Timestamps do not destabilize identity hashes
CASE= Worker execution duration may vary. This must not change the `result_id` for identical outputs.
SOURCE_PATH= scripts/integration_contract.py (validate_durable_result)
MECHANISM= The `identity` dictionary passed to `_canonical_hash` explicitly excludes `execution_start_at` and `execution_end_at`.
EXPECTED= Identical artifacts in the same `dispatch_id` yield identical `result_id`, regardless of execution timing.
ACTUAL= Timestamps are excluded from the canonical identity hash.
PASS|DEFECT= PASS

### 6. Restart/Replay tracks `restarted_at`
CASE= When a worker goes stale and the task is reclaimed, the timestamp is logged.
SOURCE_PATH= server/app.py (reclaim_stale)
MECHANISM= `task["restarted_at"] = time.time()` is recorded when transitioning to `HUMAN_REQUIRED`.
EXPECTED= Reclaim actions are timestamped.
ACTUAL= Reclaim actions are timestamped.
PASS|DEFECT= PASS
