# Courier Failure Semantics Audit — 2026-09-28

**Audit Authority**: GOOGLE_CLI / MUSE (Read-Only QA Parity)  
**Status**: 100% COMPLETE & DURABLE  
**Scope**: 12 Critical Path Failure Semantics Invariants  
**Reference Pointers**: [`ops/ai/WALL_SYSTEM.md`](file:///Users/user/Downloads/2026-courier/ops/ai/WALL_SYSTEM.md), [`ops/ai/WALL_QUEUE_CURRENT.md`](file:///Users/user/Downloads/2026-courier/ops/ai/WALL_QUEUE_CURRENT.md)  

---

## 1. Executive Summary

This audit assesses the 12 failure semantics invariants governing the Courier core engine on the critical path to Core Freeze (`candidate-b-1` @ `4c1e24ccc522042af826bc4c2b595daf85d097f9`). 

All 12 cases are classified with their expected behavior, current durable evidence, remaining gaps, gate impact, and smallest retest triggers.

---

## 2. The 12 Failure Semantics Audits

### Case 1: FAILED execution cannot become PASS by retry
- **CASE**: `FAILED_CANNOT_BECOME_PASS_BY_RETRY`
- **EXPECTED_BEHAVIOR**: If an attempt fails, that attempt is permanently recorded as `FAILED` in durable state. A retry must increment `attempt_id` (`attempt-2`), generating a distinct execution record. Historical `attempt-1` is immutable and never edited to `PASS`.
- **CURRENT_EVIDENCE**: `server/app.py` persists attempts in append-only dictionary; [`ops/ai/RETURNED_RESULT_POLICY.md`](file:///Users/user/Downloads/2026-courier/ops/ai/RETURNED_RESULT_POLICY.md) line 15 strictly forbids state mutation.
- **GAP**: NONE in data model. Verifier loop error-handling wrap (Q027 Defect #2) ensures failed attempts do not starve subsequent tasks.
- **GATE_IMPACT**: P3 Proof Level / Core Freeze invariant.
- **SMALLEST_RETEST**: `pytest tests/test_p3_server_idempotency.py -k "test_attempt_isolation"`

### Case 2: Conflicting replay cannot overwrite canonical Result
- **CASE**: `CONFLICTING_REPLAY_CANNOT_OVERWRITE_CANONICAL`
- **EXPECTED_BEHAVIOR**: Replaying a result for an already-verified `(task_id, attempt_id)` with mutated status, worker ID, or artifact hashes must be rejected with HTTP 409 Conflict. Stored canonical state is unchanged.
- **CURRENT_EVIDENCE**: `server/app.py:367` duplicate comparison logic; `tests/test_p3_server_idempotency.py`.
- **GAP**: On Base `4c1e24cc`, line 367 checks only 3-tuple `(dispatch_id, result_id, status)`. The Windows Central Writer fix packet expands this check to the full 5-tuple + artifacts digest.
- **GATE_IMPACT**: Pre-Codex 12-Case Matrix Case 12 blocker.
- **SMALLEST_RETEST**: `pytest tests/test_p3_server_idempotency.py -k "test_duplicate_rejection_conflicting"`

### Case 3: Malformed artifact target fails closed
- **CASE**: `MALFORMED_ARTIFACT_TARGET_FAILS_CLOSED`
- **EXPECTED_BEHAVIOR**: Artifact paths containing `../`, leading slashes, null bytes, or non-whitelisted characters are rejected with HTTP 400 Bad Request; target never escapes isolated directory.
- **CURRENT_EVIDENCE**: `scripts/courier_verifier.py` path normalization; verified in `tests/test_artifact_upload_flow.py`.
- **GAP**: NONE. Fully proven.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: `pytest tests/test_artifact_upload_flow.py -k "traversal"`

### Case 4: Wrong server bytes fail verification
- **CASE**: `WRONG_SERVER_BYTES_FAIL_VERIFICATION`
- **EXPECTED_BEHAVIOR**: Verifier downloads server bytes and streams into `hashlib.sha256()`. If computed hash does not match expected hash, verification returns non-zero exit code / FAIL.
- **CURRENT_EVIDENCE**: `scripts/courier_verifier.py:verify_artifacts()`; verified in `tests/test_artifact_upload_flow.py:test_verifier_checks_expected_sha256`.
- **GAP**: NONE on server-byte verification path.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: `pytest tests/test_artifact_upload_flow.py -k "test_verifier_checks_expected_sha256"`

### Case 5: Missing expected artifact cannot bypass expectation
- **CASE**: `MISSING_EXPECTED_ARTIFACT_CANNOT_BYPASS`
- **EXPECTED_BEHAVIOR**: If task specifies `expected_artifacts: {"result.txt": "sha..."}`, and worker result payload omits `"result.txt"`, verifier must detect omission and fail verification with `ARTIFACT_MISSING`.
- **CURRENT_EVIDENCE**: Base `4c1e24cc` verifier iterated over worker result artifacts rather than task expectations (12-case matrix Case 1 & 2 FAIL on base).
- **GAP**: Defect #1 in Central Writer fix packet: iterate over `task["expected_artifacts"]` and assert presence in worker payload.
- **GATE_IMPACT**: Pre-Codex 12-Case Matrix Case 1 & 2 blocker.
- **SMALLEST_RETEST**: `pytest tests/test_artifact_upload_flow.py -k "test_verifier_rejects_result_omitting_task_expected_artifact"`

### Case 6: Stale dispatch generation rejected
- **CASE**: `STALE_DISPATCH_GENERATION_REJECTED`
- **EXPECTED_BEHAVIOR**: Submission containing `attempt_id` strictly less than active attempt is rejected with HTTP 409 Conflict.
- **CURRENT_EVIDENCE**: `server/app.py` checks `attempt_id == active_dispatches[task_id]["attempt_id"]`; verified in `tests/test_p3_server_idempotency.py`.
- **GAP**: NONE. Fully proven.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: `pytest tests/test_p3_server_idempotency.py -k "generation"`

### Case 7: Changed worker rejected
- **CASE**: `CHANGED_WORKER_REJECTED`
- **EXPECTED_BEHAVIOR**: If Task is dispatched to `worker-A`, a result submitted with `worker-B` or an ACK replay from `worker-B` must be rejected.
- **CURRENT_EVIDENCE**: Dispatch lease binds `worker_id`; duplicate ACK on Base `4c1e24cc` lacked `worker_id` in 3-tuple match.
- **GAP**: Fixed in Central Writer patch by checking 5-tuple (`task_id`, `attempt_id`, `worker_id`, `status`, `artifacts_hash`).
- **GATE_IMPACT**: Pre-Codex 12-Case Matrix Case 12 blocker.
- **SMALLEST_RETEST**: `pytest tests/test_p3_server_idempotency.py -k "worker_id"`

### Case 8: Changed status rejected
- **CASE**: `CHANGED_STATUS_REJECTED`
- **EXPECTED_BEHAVIOR**: An attempt submitted as `SUCCESS` cannot be replayed or updated to `FAILED`. Submitting differing status for same attempt returns HTTP 409 Conflict.
- **CURRENT_EVIDENCE**: `server/app.py` checks `status == prior_result["status"]`; verified in `test_p3_server_idempotency.py`.
- **GAP**: NONE. Fully proven.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: `pytest tests/test_p3_server_idempotency.py -k "status_conflict"`

### Case 9: Changed attempt rejected
- **CASE**: `CHANGED_ATTEMPT_REJECTED`
- **EXPECTED_BEHAVIOR**: Submissions with unassigned, decremented, or out-of-sequence attempt IDs fail intake validation.
- **CURRENT_EVIDENCE**: `server/app.py` enforces integer equality against active dispatch.
- **GAP**: NONE. Fully proven.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: `pytest tests/test_p3_server_idempotency.py -k "attempt"`

### Case 10: Restart uncertainty remains UNKNOWN
- **CASE**: `RESTART_UNCERTAINTY_REMAINS_UNKNOWN`
- **EXPECTED_BEHAVIOR**: An interrupted run with unverified or missing execution artifacts remains `UNKNOWN_EXECUTION_STATE` or `NEEDS_VERIFICATION`. It is never assumed to be PASS.
- **CURRENT_EVIDENCE**: [`ops/ai/RETURNED_RESULT_POLICY.md`](file:///Users/user/Downloads/2026-courier/ops/ai/RETURNED_RESULT_POLICY.md) line 15; [`ops/ai/MAC_RESTART_MATRIX_EVIDENCE_PACKET_2026-09-28.md`](file:///Users/user/Downloads/2026-courier/ops/ai/MAC_RESTART_MATRIX_EVIDENCE_PACKET_2026-09-28.md) Scenario S6.
- **GAP**: NONE. Policy and execution harness enforce fail-closed state.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: Verification of restart scenario S6 in `MAC_RUN2_RESTART_EXECUTION_HARNESS_2026-09-28.md`.

### Case 11: Provider outage does not reset logical identity
- **CASE**: `PROVIDER_OUTAGE_PRESERVES_IDENTITY`
- **EXPECTED_BEHAVIOR**: Temporary provider outages (429 rate limit or 503 unavailable) trigger isolated exponential backoff; task identity and goal association remain intact.
- **CURRENT_EVIDENCE**: Documented in [`ops/ai/coordination_reports/FAMILY_25_MOTOR_PROOF_SYNTHESIS.md`](file:///Users/user/Downloads/2026-courier/ops/ai/coordination_reports/FAMILY_25_MOTOR_PROOF_SYNTHESIS.md).
- **GAP**: NONE. Fully proven.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: Mock provider timeout in unit tests.

### Case 12: Failed dispatch does not create duplicate-active execution
- **CASE**: `FAILED_DISPATCH_NO_DUPLICATE_ACTIVE`
- **EXPECTED_BEHAVIOR**: If a network failure occurs while dispatching a task to a worker, state rolls back cleanly to `READY`. No orphaned active dispatch lease remains.
- **CURRENT_EVIDENCE**: `server/app.py` transaction rollback handling; verified in [`ops/ai/coordination_reports/FAMILY_25_MOTOR_PROOF_SYNTHESIS.md`](file:///Users/user/Downloads/2026-courier/ops/ai/coordination_reports/FAMILY_25_MOTOR_PROOF_SYNTHESIS.md).
- **GAP**: NONE. Fully proven.
- **GATE_IMPACT**: PASS.
- **SMALLEST_RETEST**: `pytest tests/test_p3_server_idempotency.py -k "dispatch_rollback"`
