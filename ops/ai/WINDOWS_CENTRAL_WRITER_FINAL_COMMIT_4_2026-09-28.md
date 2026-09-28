# Windows Central Writer - Fourth Batch of 3 Substeps

Continuing the execution protocol, we completed another 3 concrete substeps (bug fixes and tests) directly in the `2026-courier` repo as the authorized Windows Worker.

### 1. AI-Generated Plan Duplicate Task ID (Bug Fix & Test)
- **Problem**: In `server/app.py`, `submit_goal` properly tracked and blocked duplicate `task_id`s from user-supplied `workflow_plan`s. However, if the plan was AI-generated via `ChiefCommander`, the steps were blindly appended without checking `seen_tasks` or `state["tasks"]`. A hallucinated or duplicate task ID would silently overwrite global state.
- **Fix**: Abstracted the duplicate validation logic (`seen_tasks` & `state.get("tasks", {})` lookup) to apply universally across both user-supplied and AI-generated workflow plan branches.
- **Evidence**: Created and passed `test_goal_with_ai_generated_duplicate_task_id_fails` in `tests/test_p3_server_idempotency.py`.

### 2. Windows Daemon Resource Pressure Result Hoarding (Bug Fix & Test)
- **Problem**: In `scripts/windows_worker/daemon.py`, the `loop()` throttled worker execution if `is_resource_pressure_high()` was True. However, this check applied blindly to all loop iterations, even if the worker phase was already `RESULT_READY`. If CPU pressure was high, the worker would repeatedly pause and fail to upload its artifacts or deliver its final JSON result to the server, hoarding it unnecessarily.
- **Fix**: Adjusted the throttle condition to `if (not task or task.get("worker_phase") == "CLAIMED") and is_resource_pressure_high():`. This ensures execution and claiming back off under pressure, but result delivery proceeds immediately.
- **Evidence**: Created and passed `test_resource_pressure_does_not_block_result_ready_phase` in `tests/test_windows_worker_contract.py`.

### 3. Register Worker Quarantine State Inconsistency (Bug Fix)
- **Problem**: In `server/app.py` `register_worker`, when a worker re-registered with lost state (`WORKER_RESTARTED_AND_LOST_STATE`), it quarantined the task (`HUMAN_REQUIRED`) and blocked the goal (`BLOCKED`), but failed to sync the `HUMAN_REQUIRED` status back to the workflow plan step. Any human or AI reading the `workflow_plan` via `GET /walls` would incorrectly see the step still as `DISPATCHED`.
- **Fix**: Added synchronization loop within `register_worker` to ensure `step["status"]` and `step["recovery_reason"]` are explicitly set to `HUMAN_REQUIRED` and `WORKER_RESTARTED_AND_LOST_STATE` respectively.
- **Evidence**: Direct code inspection and fix applied to `server/app.py`. Tests passed perfectly.

---
Commit SHA: (Pending commit)
All tests (`pytest tests/`) are 100% passing across the suite.
