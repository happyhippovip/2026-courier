# Family 7: Restart Matrix & A4 Recovery Preparation

**Status**: READY FOR CORE FREEZE  
**Host**: MAC / CROSS-PLATFORM  
**Reference**: `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md` (Gate 4)

---

## 1. Concrete Failure & Recovery Taxonomy

### Scenario 1: Courier Coordinator Process Restart
- **EXPECTED_STATE**: Coordinator reloads JSON state atomically. Reconciled tasks remain `RECONCILED` with `attempts` unchanged. Queued/Dispatched tasks resume from their last persistent state without blind replay.
- **PROOF_REQUIRED**: Verification that `PHYS-003` restart preserved `canary-task-a` at `attempts == 1` and auto-dispatched `run2-task-b`.
- **TEST_OR_PHYSICAL**: Physical Canary (`PHYS-003`) & `tests/test_mac_worker_recovery.py`.
- **FAILURE_CONDITION**: Coordinator increments attempt on restart, replays Step A, or resets `current_step_index`.

### Scenario 2: Worker Disappears / Unresponsive
- **EXPECTED_STATE**: Stale worker detected when `now - last_seen > 300s`. Dispatched step marked `HUMAN_REQUIRED` with `recovery_reason = "STALE_WORKER_EFFECT_AMBIGUOUS"`. Worker marked `available = False`. Goal marked `BLOCKED`.
- **PROOF_REQUIRED**: Server endpoint `POST /tasks/reclaim_stale` quarantines task without replaying effect.
- **TEST_OR_PHYSICAL**: Test `tests/test_server_integration_contract.py::test_stale_claim_is_quarantined_without_replay_and_other_goal_continues`.
- **FAILURE_CONDITION**: Blind re-dispatch to another worker while ambiguous effects exist on disk/network.

### Scenario 3: Result Persisted / Reconcile Missing
- **EXPECTED_STATE**: Task status remains `RESULT_RECEIVED`. Verifier polls `/tasks/pending_verification`, downloads server copy, re-hashes, posts verdict to `/tasks/verify`, transitioning to `RECONCILED`.
- **PROOF_REQUIRED**: Verifier loop picks up pending task independently of worker lifecycle.
- **TEST_OR_PHYSICAL**: `tests/test_artifact_upload_flow.py::test_windows_worker_uploads_and_verifier_reconciles`.
- **FAILURE_CONDITION**: Task stays permanently stuck in `RESULT_RECEIVED` or is claimed as new by a worker.

### Scenario 4: READY Before Dispatch
- **EXPECTED_STATE**: Task remains `QUEUED` until an authorized worker matching capability registers and posts `/tasks/claim`.
- **PROOF_REQUIRED**: Task claim endpoint leases task, transitions to `DISPATCHED`, generates fresh `dispatch_id`.
- **TEST_OR_PHYSICAL**: `tests/test_server_integration_contract.py::test_concurrent_claims_have_exactly_one_winner`.
- **FAILURE_CONDITION**: Multiple workers claim the same `task_id` concurrently.

### Scenario 5: Dispatch Happened / Result Missing
- **EXPECTED_STATE**: Task remains `DISPATCHED` within lease timeout. If heartbeat expires, transitions to `HUMAN_REQUIRED`.
- **PROOF_REQUIRED**: Worker recovery logic or operator resume `/tasks/<id>/resume` required to reset.
- **TEST_OR_PHYSICAL**: `tests/test_p3_server_idempotency.py::test_failed_verification_can_be_resumed_with_new_attempt`.
- **FAILURE_CONDITION**: Task silently vanishes or state resets to blank.

### Scenario 6: Temporary Provider / Network Unavailable
- **EXPECTED_STATE**: Worker retains local state and retries upload with exponential backoff; does NOT re-execute underlying tool command.
- **PROOF_REQUIRED**: Worker harness verifies upload retry on 503/network fault with `executions == [1]`.
- **TEST_OR_PHYSICAL**: `tests/test_artifact_upload_flow.py::test_windows_transient_upload_failure_keeps_result_without_reexecution`.
- **FAILURE_CONDITION**: Worker re-runs command upon network drop, producing duplicate external side-effects.

### Scenario 7: Stale Result Arrival
- **EXPECTED_STATE**: Result submitted with mismatched `dispatch_id` or superseded `attempt_id` rejected with HTTP 400.
- **PROOF_REQUIRED**: `validate_durable_result` asserts `result["dispatch_id"] == task["dispatch_id"]`.
- **TEST_OR_PHYSICAL**: `tests/test_result_identity_binding.py::test_prior_attempt_or_dispatch_evidence_fails_closed`.
- **FAILURE_CONDITION**: Superseded result overwrites newer attempt or alters task status.

### Scenario 8: Identical Duplicate Result
- **EXPECTED_STATE**: Coordinator acknowledges duplicate idempotently with `{"status": "ACK_DUPLICATE"}` and HTTP 200. Attempts count and status unchanged.
- **PROOF_REQUIRED**: Server endpoint `/tasks/result` checks stored result identity.
- **TEST_OR_PHYSICAL**: `tests/test_p3_server_idempotency.py::test_resent_result_is_acknowledged_idempotently`.
- **FAILURE_CONDITION**: Re-submission causes duplicate attempt increment or double reconciliation.

### Scenario 9: Conflicting Duplicate Result
- **EXPECTED_STATE**: Conflicting result for processed task rejected with HTTP 409 Conflict.
- **PROOF_REQUIRED**: Server rejects altered status/result_id on processed tasks.
- **TEST_OR_PHYSICAL**: `tests/test_p3_server_idempotency.py::test_conflicting_result_for_processed_task_is_rejected`.
- **FAILURE_CONDITION**: Stored result overwritten by subsequent divergent payload.

---

## 2. Autonomy Grade A4 Attestation Checklist
- [x] Coordinator state mutations serialized via file mutex.
- [x] Worker crash / disappearance quarantines rather than blinds replays.
- [x] Zero human relay between Step A and Step B under normal execution.
- [x] Transient network drop preserves executed effect without double-execution.
- [x] Superseded attempts strictly fail closed.
