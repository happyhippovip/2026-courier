# Family 03: Final Candidate Evidence Hardening

**Slot**: MAC-MEGA-003  
**Mode**: READ_ONLY_PLUS_COORDINATION_REPORTS  
**Status**: AUDITED & GROUNDED (WAITING_FOR_FINAL_SHA)  
**Base SHA**: `4c1e24ccc522042af826bc4c2b595daf85d097f9` (`candidate-b-1`)  
**Primary Source Evidence**:
- `ops/ai/wall_results/POST200-021_result.md`
- `ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md`
- `ops/ai/coordination_reports/FAMILY_01_HARVEST_DELTA_MAC-MEGA-002.md`

---

## 1. Executive Summary

Work Family 03 establishes the evidence baseline for the final candidate code before Codex review. It ensures:
1. Every acceptance case is grounded in executed pytest node IDs, code inspection, or physical run proofs.
2. Contradicted cases on base `4c1e24cc` are isolated strictly to the 4 known defects packaged for the Windows Central Writer.
3. Both empty-list and partial-omission artifact sub-cases (Adjudication Note A1) are formally mapped and tracked.
4. No base-bound test passes are falsely claimed as final; all evidence triggers mandatory re-test against `FINAL_SHA`.

---

## 2. Acceptance Matrix Evidence Grounding

| Case # | Acceptance Invariant | Current Base Verdict | Concrete Evidence / Test Node | Required Post-CW Action |
|:---:|---|:---:|---|---|
| **1** | Task-owned expected hash survives flow | `CONTRADICTED` | `scripts/courier_verifier.py:78` reads `art["expected_sha256"]` | CW: Derive expected hash strictly from `task["expected_artifacts"]` / `task["expected_sha256"]`. |
| **2** | Correct server bytes PASS | `PROVEN_EXECUTED` | `tests/test_artifact_upload_flow.py::test_verifier_independently_hashes_server_copy_and_detects_tampering` | Re-run on `FINAL_SHA` (must stay green). |
| **3** | Wrong bytes FAIL | `PROVEN_EXECUTED` | `tests/test_artifact_upload_flow.py::test_verifier_checks_expected_sha256` | Re-run on `FINAL_SHA` (must stay green). |
| **4** | Worker expected hash rejected | `CONTRADICTED` | `scripts/integration_contract.py:156` permits worker `expected_sha256` | CW: Disallow `"expected_sha256"` in `result["artifacts"]` schema. |
| **5a** | Omission: Empty artifact list rejected | `PROVEN_EXECUTED` | `tests/test_artifact_upload_flow.py:382` (`empty_list_rejected`) | Re-run on `FINAL_SHA`. |
| **5b** | Omission: Partial task artifact omitted | `FAIL_ON_BASE` | `scripts/courier_verifier.py` missing task-declared check | CW: Add check that every artifact in `task["expected_artifacts"]` is present in result. |
| **6** | No task expectation remains legacy only | `PROVEN_EXECUTED` | `tests/test_artifact_upload_flow.py::test_remote_worker_result_must_upload_artifacts` | Remote uploads mandatory; local file opens blocked. |
| **7** | Malformed/ambiguous target FAIL | `PROVEN_EXECUTED` | `tests/test_artifact_upload_flow.py::test_poison_pill_task_payload_does_not_crash_verifier` | Traversal (`..`), null bytes, invalid IDs fail closed. |
| **8** | Identical replay ACK | `PROVEN_EXECUTED` | `tests/test_p3_server_idempotency.py::test_resent_result_is_acknowledged_idempotently` | Returns HTTP 200 `ACK_DUPLICATE`; zero attempt increment. |
| **9** | Changed status rejected | `PROVEN_EXECUTED` | `tests/test_p3_server_idempotency.py::test_conflicting_result_status_is_rejected` | Conflicting status returns HTTP 409 Conflict. |
| **10** | Changed worker rejected | `PROVEN_CODE` | `server/app.py:372`, `scripts/integration_contract.py:138` | Worker mismatch fails contract validation with HTTP 400. |
| **11** | Changed attempt/dispatch rejected | `PROVEN_EXECUTED` | `tests/test_p3_server_idempotency.py::test_superseded_attempt_is_rejected` | Superseded dispatch returns HTTP 400. |
| **12** | Changed metadata / artifact rejected | `FAIL_ON_BASE` | `server/app.py:367` check omits `worker_id` / `attempt_id` | CW: Expand duplicate comparison in line 367 to include `worker_id` & `attempt_id`. |

---

## 3. Retest Protocol for FINAL_SHA

Upon publication of `FINAL_SHA` by the Windows Central Writer:
1. Re-run targeted test suite (44+ tests, zero skipped).
2. Execute compile check across the 5 authorized files (`py_compile`).
3. Run `git diff --check` to verify trailing whitespace removal.
4. Transition all 12 matrix cases to `PASS_PROVEN`.
5. Only then set `PRE_CODEX_READY=YES`.

DO_NOT_REPEAT_FINGERPRINT=sha256-16f9455fe02d8470
