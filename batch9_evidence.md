# Batch 9 Evidence

### Substep 1: Worker FAILED_TERMINAL Hides Goal from `/walls`
**Problem:** When a worker reported a failure and exhausted retries (reaching `FAILED_TERMINAL`), `server/app.py` correctly marked the task `FAILED_TERMINAL`, but left the parent goal `ACTIVE`. Because the `/walls` endpoint ONLY returns goals marked `BLOCKED`, the failure was completely invisible to operators and recovery loops.
**Fix:** Modified `server/app.py` in `task_result()` to explicitly transition the goal to `BLOCKED` when a task hits `FAILED_TERMINAL`.
**Evidence:** Wrote `test_worker_failure_blocks_goal` in `tests/test_p3_server_idempotency.py` which validates that a worker's terminal failure makes the parent goal `BLOCKED`. Test passes.

### Substep 2: Long-running Windows Tasks False Positive Quarantine
**Problem:** In `scripts/windows_worker/daemon.py`, `run_task()` uses `process.communicate(timeout=600)` and waits synchronously without sending heartbeats. However, `server/app.py` `reclaim_stale()` quarantines workers if they miss heartbeats for `300` seconds (5 minutes). This meant any task running between 5 and 10 minutes would silently trigger a `STALE_WORKER_EFFECT_AMBIGUOUS` quarantine race condition. 
**Fix:** Added a background heartbeat thread inside `run_task()` that loops while `process.communicate()` is waiting.

### Substep 3: Windows Artifact Upload Rejection Dropped Tasks
**Problem:** In `scripts/windows_worker/daemon.py`, if an artifact upload was permanently rejected (e.g. 413 Payload Too Large), the daemon treated it the same way as a rejected `/tasks/result` POST: it released the task and expected the server to quarantine it with `WORKER_RESTARTED_AND_LOST_STATE`. This swallowed the actual upload failure reason.
**Fix:** Disambiguated `upload_pending_artifacts` rejection from `http_post_result` rejection. Converted upload rejections into a clean `FAILED` result payload (appending "Artifact upload permanently rejected" to stderr), posting the failure back to the server so it is accurately logged and tracked. Updated `test_windows_artifact_changed_after_hashing_is_released_not_uploaded` assertion to expect `QUEUED` instead of the old buggy behavior.

All tests passed successfully!
