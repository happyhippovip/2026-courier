# Windows Central Writer - Sixth Batch of 3 Substeps

Continuing the execution protocol, we completed another 3 concrete substeps directly in the `2026-courier` repo as the authorized Windows Worker.

### 1. Workflow Plan Type Validation (Bug Fix & Test)
- **Problem**: In `server/app.py` `submit_goal`, `data["workflow_plan"]` lacked type validation. If a dictionary was sent instead of a list, the subsequent iteration over `goal["workflow_plan"]` would iterate over string keys, leading to `TypeError: 'str' object does not support item assignment` on `step["goal_id"] = goal_id` and a 500 server crash.
- **Fix**: Added explicit `isinstance(data["workflow_plan"], list)` validation, returning a clean 400 error.
- **Evidence**: Added and passed `test_workflow_plan_must_be_list` in `tests/test_p3_server_idempotency.py`.

### 2. Missing Tests for Reclaim Stale Quarantine (Test Completion)
- **Problem**: The server's `reclaim_stale` function (mounted at `/tasks/reclaim_stale`), which identifies timed-out workers and quarantines their dispatched tasks (to `HUMAN_REQUIRED`), was entirely untested. This logic is critical for idempotency.
- **Fix**: Wrote a full integration test mocking a stale worker timeout and validating the task state transition.
- **Evidence**: Added and passed `test_reclaim_stale_quarantines_ambiguous_tasks` in `tests/test_p3_server_idempotency.py`.

### 3. Workflow Plan Instruction Validation (Bug Fix & Test)
- **Problem**: In `server/app.py` `submit_goal`, `step["instruction"]` lacked string validation. If an object/list was sent, the Windows worker would inherit this complex type and crash inside PowerShell base-64 text encoding (`windows_worker/daemon.py`).
- **Fix**: Added strict type validation (`isinstance(step["instruction"], str)`) in `submit_goal` when an instruction is present.
- **Evidence**: Added and passed `test_workflow_plan_step_instruction_must_be_string` in `tests/test_p3_server_idempotency.py`.

---
Commit SHA: (Pending commit)
All server/windows tests are passing. Note: A Mac-specific teardown permission error (`test_muse_supervisor.py`) appeared during global suite run, which is outside the Windows Writer's jurisdiction and not caused by these cross-platform server fixes.
