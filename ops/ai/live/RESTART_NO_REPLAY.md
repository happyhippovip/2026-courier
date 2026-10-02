# RESTART / NO-REPLAY DEEP PASS

## Status: VERIFIED (GREEN)

### 1. Restart vor Result-Persist
CASE= Worker restart before result upload is completed.
SOURCE_PATH= server/app.py (register_worker)
STATE_BEFORE= DISPATCHED
INTERRUPTION= Worker process crash, local state lost.
STATE_AFTER_RESTART= HUMAN_REQUIRED
EXPECTED= HUMAN_REQUIRED (Safe quarantine)
ACTUAL= HUMAN_REQUIRED
PASS|DEFECT= PASS
MISSING_TEST= Covered by idempotency/registration tests.

### 2. Restart nach Result-Persist
CASE= Worker restart after `/tasks/result` completes but before verify.
SOURCE_PATH= server/app.py (register_worker)
STATE_BEFORE= RESULT_RECEIVED
INTERRUPTION= Worker process crash, local state lost.
STATE_AFTER_RESTART= RESULT_RECEIVED
EXPECTED= RESULT_RECEIVED (No quarantine needed, result is safe).
ACTUAL= RESULT_RECEIVED
PASS|DEFECT= PASS
MISSING_TEST= None

### 3. Lost ACK / identischer Resend
CASE= Worker resends the exact same result payload because it lost the HTTP ACK.
SOURCE_PATH= server/app.py (task_result)
STATE_BEFORE= RESULT_RECEIVED
INTERRUPTION= Network timeout on ACK, worker retries upload.
STATE_AFTER_RESTART= RESULT_RECEIVED
EXPECTED= ACK_DUPLICATE
ACTUAL= ACK_DUPLICATE
PASS|DEFECT= PASS
MISSING_TEST= None

### 4. stale worker reconnect
CASE= Worker disappears for >5 minutes, task is quarantined via `/tasks/reclaim_stale`, then worker tries to upload result.
SOURCE_PATH= server/app.py (reclaim_stale, task_result)
STATE_BEFORE= HUMAN_REQUIRED (due to reclaim)
INTERRUPTION= Worker tries to post result.
STATE_AFTER_RESTART= HUMAN_REQUIRED
EXPECTED= 409 Task is not awaiting a result
ACTUAL= 409 Task is not awaiting a result
PASS|DEFECT= PASS
MISSING_TEST= None

### 5. stale attempt result
CASE= Worker uploads result for an old `attempt_id` after a retry has advanced the `attempt_id`.
SOURCE_PATH= server/app.py (task_result)
STATE_BEFORE= DISPATCHED (with new attempt_id)
INTERRUPTION= Old worker thread/process posts old attempt_id payload.
STATE_AFTER_RESTART= DISPATCHED
EXPECTED= 400 ContractError (attempt_id mismatch)
ACTUAL= 400 ContractError
PASS|DEFECT= PASS
MISSING_TEST= None

### 6. duplicate result
CASE= Worker tries to submit a different result for an already completed task.
SOURCE_PATH= server/app.py (task_result)
STATE_BEFORE= RECONCILED
INTERRUPTION= New result uploaded for same task.
STATE_AFTER_RESTART= RECONCILED
EXPECTED= 409 Conflicting result for already processed task
ACTUAL= 409 Conflicting result
PASS|DEFECT= PASS
MISSING_TEST= None

### 7. Retry erzeugt neue Attempt/Dispatch/Run Identity
CASE= A failed task is retried via `/tasks/{task_id}/resume`.
SOURCE_PATH= server/app.py (resume_task, claim_task)
STATE_BEFORE= FAILED_VERIFICATION
INTERRUPTION= Admin triggers retry, worker claims it.
STATE_AFTER_RESTART= DISPATCHED
EXPECTED= attempts incremented, attempt_id updated, dispatch_id updated.
ACTUAL= attempts incremented, attempt_id/dispatch_id minted on claim.
PASS|DEFECT= PASS
MISSING_TEST= None

### 8. FAILED-Versuch bleibt dauerhaft sichtbar
CASE= A task is retried, but the old failure needs to remain observable.
SOURCE_PATH= server/app.py (task_result, resume_task)
STATE_BEFORE= RESULT_RECEIVED (FAIL)
INTERRUPTION= Retry triggered.
STATE_AFTER_RESTART= QUEUED
EXPECTED= Old result appended to `failure_history`, task `resumed_from` captures transition.
ACTUAL= `failure_history` retains the result object, `resumed_from` records `FAILED_VERIFICATION`.
PASS|DEFECT= PASS
MISSING_TEST= None
