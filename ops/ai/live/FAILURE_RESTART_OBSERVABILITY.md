# FAILURE PRESERVATION / RESTART / OBSERVABILITY

## Status: VERIFIED (GREEN)

### 6. Failure Preservation
**Verified.** When `/tasks/verify` is called with `verdict: FAIL`, the task status changes to `FAILED_VERIFICATION` and the overall goal is set to `BLOCKED`. The failed result context is strictly preserved without being overwritten.

### 7. Restart S1-S9
**Verified.** Calling the resume/retry endpoint (`/tasks/{task_id}/resume` with `{"action": "retry"}`) correctly transitions the task back to `QUEUED` and unblocks the goal (`ACTIVE`). The entire sequence S1-S9 can seamlessly restart for that step.

### 8. Evidence / Observability
**Verified.** The system retains explicit auditability of the retry mechanism. The task state explicitly records `resumed_from = FAILED_VERIFICATION` to provide observability that this is a second (or subsequent) attempt following a verified failure.

## Regression Evidence
Tested natively via `tests/test_marathon.py` (`test_marathon_units_4_to_8`) tracking the preservation, resumption, and audit trails flawlessly.
