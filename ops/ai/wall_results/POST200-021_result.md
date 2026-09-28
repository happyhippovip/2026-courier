# Result for POST200-021: Final 12 Acceptance Case Evidence Mapping

- **TASK_ID**: POST200-021
- **ROLE**: FINAL_12_CASE_EVIDENCE
- **STATUS**: RECONCILED
- **VERDICT**: PASS (AUDIT & CLASSIFICATION COMPLETE)
- **INPUTS_READ**:
  - `server/app.py`
  - `scripts/courier_verifier.py`
  - `scripts/integration_contract.py`
  - `scripts/artifact_store.py`
  - `tests/test_artifact_upload_flow.py`
  - `tests/test_p3_server_idempotency.py`
  - `ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md`
- **TARGETED_TESTS_RUN**:
  - `tests/test_p3_server_idempotency.py` (8/8 passed in 0.64s)
  - `tests/test_artifact_upload_flow.py` (25/25 passed in 6.21s)
- **DO_NOT_REPEAT**: `post200-021-final-12-case-evidence-complete`

---

## Final 12 Case Classification Matrix

| # | Case Name | Classification | Code Reference | Test / Operational Evidence | Status Summary |
|---|---|---|---|---|---|
| 1 | **task-owned expected hash survives flow** | `CONTRADICTED` | `scripts/courier_verifier.py:78`, `scripts/integration_contract.py:156` | `tests/test_artifact_upload_flow.py:143-164` | Current code checks worker-supplied `art["expected_sha256"]`, not `task["expected_sha256"]`. Task-owned hash decoupling queued for Windows Central Writer. |
| 2 | **correct server bytes PASS** | `PROVEN_BY_EXECUTED_TEST` | `scripts/courier_verifier.py:54-91`, `server/app.py:466-515` | `tests/test_artifact_upload_flow.py:49-58, 126-141, 265-284, 327-381`; `PHYS-002` Canary A->VERIFY->B | Independently verified server copy matches, verifier issues PASS, server reconciles task to `RECONCILED`. 33/33 tests green. |
| 3 | **wrong bytes FAIL** | `PROVEN_BY_EXECUTED_TEST` | `scripts/courier_verifier.py:79-81`, `scripts/artifact_store.py:149-151` | `tests/test_artifact_upload_flow.py:137-139, 155-164` | Tampered server copy or mismatched SHA256 immediately returns `FAIL`. |
| 4 | **worker expected hash rejected** | `CONTRADICTED` | `scripts/integration_contract.py:156`, `scripts/courier_verifier.py:78` | Missing rejection test (`MISSING_TEST`) | Vulnerability exists in base: worker artifact dictionary is permitted to inject `expected_sha256`. Queued for Windows Central Writer. |
| 5 | **omission cannot bypass expectation** | `PROVEN_BY_EXECUTED_TEST` | `scripts/courier_verifier.py:62-68`, `scripts/integration_contract.py:150-151` | `tests/test_artifact_upload_flow.py:382-396, 177-180` | Omission of required artifact returns `FAIL`; successful result with empty artifacts rejected by contract validation. |
| 6 | **no task expectation remains legacy only** | `PROVEN_BY_EXECUTED_TEST` | `scripts/courier_verifier.py:86-90`, `server/app.py:377-380` | `tests/test_artifact_upload_flow.py:167-175` | Remote workers (Mac/Windows) strictly rejected if artifact is not uploaded to server store; verifier never opens worker local paths. |
| 7 | **malformed/ambiguous target FAIL** | `PROVEN_BY_EXECUTED_TEST` | `scripts/integration_contract.py:158-171`, `scripts/artifact_store.py:87-88`, `scripts/courier_verifier.py:103-146` | `tests/test_artifact_upload_flow.py:60-69, 86-94, 397-450` | Path traversal (`..`), absolute paths, invalid artifact IDs, and poison pill tasks fail closed safely without crashing poller. |
| 8 | **identical replay ACK** | `PROVEN_BY_EXECUTED_TEST` | `server/app.py:366-368, 476-479` | `tests/test_p3_server_idempotency.py:84-89, 100-109` | Identical resend of stored result returns `{"status": "ACK_DUPLICATE"}` with HTTP 200; attempts count not incremented. |
| 9 | **changed status rejected** | `PROVEN_BY_EXECUTED_TEST` | `server/app.py:369-370` | `tests/test_p3_server_idempotency.py:92-98`, `test_server_integration_contract.py:414` | Submitting a conflicting result status for an already processed task returns HTTP 409 Conflict. |
| 10 | **changed worker rejected** | `PROVEN_BY_CODE` | `server/app.py:372`, `scripts/integration_contract.py:138-140`, `scripts/artifact_store.py:138-140` | Covered by contract mismatch in `tests/test_artifact_upload_flow.py:60-67` (`over2-400`) | Server enforces `task["worker_id"] == worker_id` (returns HTTP 400); contract validation enforces field identity. |
| 11 | **changed attempt/dispatch rejected** | `PROVEN_BY_EXECUTED_TEST` | `scripts/integration_contract.py:138-140`, `server/app.py:376-381` | `tests/test_p3_server_idempotency.py:52-65`, `tests/test_artifact_upload_flow.py:60-67` | Mismatched or superseded attempt/dispatch ID fails contract validation with HTTP 400. |
| 12 | **changed artifact result rejected** | `PROVEN_BY_EXECUTED_TEST` | `server/app.py:377-380`, `scripts/artifact_store.py:133-145` | `tests/test_artifact_upload_flow.py:86-94, 295-312` | Unknown artifact IDs, mismatched sha256 or size against server store rejected with HTTP 400; changed files after hashing transition task to `HUMAN_REQUIRED`. |

---

## Actionable Takeaway for Windows Central Writer
1. **Cases 1 & 4 Fix**: In `scripts/courier_verifier.py`, remove worker hash reliance (`art.get("expected_sha256")`). Derive expected sha256 strictly from `task["expected_artifacts"]` / `task["expected_sha256"]`.
2. **Schema Invariant**: In `scripts/integration_contract.py`, disallow `"expected_sha256"` in `result["artifacts"]` schema to prevent worker injection.
3. **Replay Invariant Check**: In `server/app.py:367`, expand duplicate comparison from `("dispatch_id", "result_id", "status")` to include `worker_id` and `attempt_id`.

DO_NOT_REPEAT_FINGERPRINT=sha256-fb8a85a1b8c5a2c9
