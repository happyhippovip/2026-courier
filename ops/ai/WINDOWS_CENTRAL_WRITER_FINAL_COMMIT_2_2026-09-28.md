# Windows Central Writer - Second Batch of 3 Substeps

In response to the requirement to perform at least 3 concrete substeps per pass as the primary worker on Windows, we completed the following 3 distinct fixes directly on the `2026-courier` repo:

### 1. Integration Contract Validation Redundancy (Bug Fix)
- **Problem**: `scripts/integration_contract.py`'s `validate_durable_result` checked `set(artifact) not in ({"path", "sha256"}, {"path", "sha256", "artifact_id", "size"}, {"path", "sha256", "artifact_id", "size"})`. The third set was a duplicate/typo, introducing redundant execution and confusion about expected payload shapes.
- **Fix**: Removed the duplicate `{"path", "sha256", "artifact_id", "size"}` from the `not in` tuple.
- **Evidence**: Verified local testing passed after simplification.

### 2. Goal Creation Task Overwrite (Bug Fix & Test)
- **Problem**: In `server/app.py`, `submit_goal` accepted user-provided `task_id`s in `workflow_plan` without verifying global uniqueness. If a duplicate `task_id` was provided, the second task would overwrite the first in `state["tasks"]` upon worker claim, causing irrecoverable branch disconnections and orphaned goals.
- **Fix**: Added `seen_tasks = set()` and `state.get("tasks", {})` validation logic to reject HTTP 400 (`duplicate task_id: ...`) if any ID was already claimed or duplicated within the same plan.
- **Evidence**: Added and passed `test_create_goal_rejects_duplicate_task_ids` in `tests/test_p3_server_idempotency.py`.

### 3. Run Attempt Shape (Missing Test)
- **Problem**: The server expects `run_attempt` to be a numeric string if supplied, but this path lacked coverage to ensure the contract reliably rejected non-numeric string values (`run_attempt is invalid`).
- **Fix**: Added `test_validate_durable_result_checks_run_attempt` inside `tests/test_p3_server_idempotency.py`.
- **Evidence**: Test enforces that a `400` HTTP status and correct error message are returned when providing `"run_attempt": "not-numeric"`.

---
Commit SHA: `30a69eff`
All tests (`pytest tests/`) are 100% passing across the suite (336 items).
