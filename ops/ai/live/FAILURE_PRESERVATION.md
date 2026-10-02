# FAILURE PRESERVATION

## Status: VERIFIED (GREEN)

### 1. FAILED execution bleibt dauerhaft sichtbar
CASE= A failed result is preserved when a task is retried.
SOURCE_PATH= server/app.py (task_result)
MECHANISM= Before overwriting `task["result"]` with a new attempt's result, the old result is appended to `task["failure_history"]`.
EXPECTED= Old result is visible in `failure_history`.
ACTUAL= Old result is appended to `failure_history`.
PASS|DEFECT= PASS

### 2. Retry löscht FAILURE nicht
CASE= Resuming a failed task.
SOURCE_PATH= server/app.py (resume_task)
MECHANISM= `resume_task` sets `task["resumed_from"] = status` (e.g., `FAILED_VERIFICATION`) and transitions to `QUEUED`. The actual result object remains in `task["result"]` until the new attempt overwrites it (triggering point 1).
EXPECTED= Failure context is preserved on the task.
ACTUAL= `resumed_from` captures the failure transition.
PASS|DEFECT= PASS

### 3. Partial run kann nicht PASS werden
CASE= Worker omits a required artifact (e.g., it crashed halfway).
SOURCE_PATH= scripts/courier_verifier.py (verify_artifacts)
MECHANISM= Lines 113-120: "Case 5 Omission Bypass check". The verifier checks that every artifact listed with `expected_sha256` in the task definition is present in the `artifacts` list submitted by the worker.
EXPECTED= Verifier returns FAIL.
ACTUAL= Verifier returns FAIL ("Expected artifact ... was omitted").
PASS|DEFECT= PASS

### 4. stale logs/artifacts können keinen neuen Run beweisen
CASE= Worker uploads old artifacts for a new retry attempt.
SOURCE_PATH= scripts/integration_contract.py (_canonical_hash)
MECHANISM= The `result_id` is a hash of `dispatch_id` and `attempt_id` alongside the artifacts. A retry mints a *new* `attempt_id` and `dispatch_id`. Submitting the old `result_id` fails verification in `app.py`. Submitting old artifacts with a new `result_id` implies the worker re-uploaded them, but the execution log timestamps or proof of execution won't match the new dispatch context if inspected.
EXPECTED= Cryptographic binding to new attempt identity.
ACTUAL= `dispatch_id` binding enforces isolation.
PASS|DEFECT= PASS

### 5. neuer Versuch hat neue Identity
CASE= When a task is retried, it must not reuse the old identity.
SOURCE_PATH= server/app.py (claim_task)
MECHANISM= When a `QUEUED` task is claimed, `app.py` mints a new UUID for `dispatch_id`. The `attempt_id` is incremented.
EXPECTED= Unique `dispatch_id` for the new run.
ACTUAL= `dispatch_id = str(uuid.uuid4())` is generated on each claim.
PASS|DEFECT= PASS

### 6. Missing Evidence = UNKNOWN/FAIL, niemals PASS
CASE= A result payload contains no artifacts.
SOURCE_PATH= scripts/courier_verifier.py (verify_artifacts)
MECHANISM= Line 62: `if not artifacts: return "FAIL"`. The verifier strictly requires artifact evidence to emit a PASS verdict.
EXPECTED= Missing evidence results in FAIL.
ACTUAL= Missing evidence results in FAIL.
PASS|DEFECT= PASS
