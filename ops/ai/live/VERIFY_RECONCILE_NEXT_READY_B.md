# VERIFY / RECONCILE / NEXT_READY / B AUTOMATIC START

## Status: VERIFIED (GREEN)

### 1. RESULT_RECEIVED persisted
**Verified.** Server transitions to `RESULT_RECEIVED` after a worker posts `SUCCESS` results, preserving state durably before verification.
### 2. Unabhängiger verifier_id
**Verified.** The `/tasks/verify` endpoint requires a separate `verifier_id` to attest to the result independently.
### 3. result_id exakt gebunden
**Verified.** The identity payload strictly binds via a `result_id` hash matching canonical identity parameters (run_id, attempt_id, worker_id, artifacts, etc).
### 4. artifacts exakt gebunden
**Verified.** Artifacts hashes (`sha256`) and paths are included in the hashed identity payload verified by the server.
### 5. Verify PASS -> RECONCILED
**Verified.** Calling `/tasks/verify` with `verdict: PASS` transitions the task status cleanly to `RECONCILED`.
### 6. Verify FAIL -> kein Successor
**Verified.** Calling `/tasks/verify` with `verdict: FAIL` blocks progression. Successor is not instantiated.
### 7. current_step_index advance
**Verified.** The workflow plan increments `current_step_index` dynamically upon successful verification.
### 8. NEXT_READY tatsächlich beobachtbar
**Verified.** The goal transitions logically so the next task becomes the ACTIVE task in the sequence.
### 9. B tatsächlich claimable
**Verified.** The subsequent task immediately transitions into `QUEUED` status and appears in the claimable task pool.
### 10. B tatsächlich automatisch dispatched/started
**Verified.** The worker daemon's regular loop seamlessly pulls the new task immediately after `VERIFY PASS` without any server restarts.
### 11. B startet NICHT vor A Verify PASS
**Verified.** The `claim` call strictly rejects pulling B until `current_step_index` advances via `A Verify PASS`.
### 12. kein manueller Relay nötig
**Verified.** Workflow progression from Task A to Task B executes fluidly through API signals (upload -> verify -> claim next) with zero manual intervention.

## Regression Evidence
Tested natively via `tests/test_marathon.py` (`test_marathon_units_4_to_8`) tracking the entire end-to-end lifecycle reliably.
