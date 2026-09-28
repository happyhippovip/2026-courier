# Google Pre-Codex Gate Audit — 2026-09-27

Status: GATE_PASSED (PRE_CODEX_READY=YES)
Generation: 2026-09-27-FINAL
Base SHA: 4c1e24ccc522042af826bc4c2b595daf85d097f9 (candidate-b-1)
Final Candidate SHA: 9f219f187a415ffef8b6c867b2ff9c26ad0a5b88
Rejected: candidate-b-2
Candidate-b-3: NOT REQUIRED

---

## 1. Pre-Codex Stop Gate Checklist

| Criterion | Target Requirement | Current State | Verdict |
|---|---|---|---|
| **BASE_SHA** | Accepted candidate-b-1 lineage | `4c1e24ccc522042af826bc4c2b595daf85d097f9` | **PASS** |
| **FINAL_SHA** | Isolated clean candidate commit | `9f219f187a415ffef8b6c867b2ff9c26ad0a5b88` | **PASS** |
| **EXACT_CHANGED_FILES** | Exactly the 5 authorized files | 4 modified, 1 unchanged (0 unexpected) | **PASS** |
| **TWELVE_CASE_MATRIX** | Complete against candidate | 12/12 PASS | **PASS** |
| **TARGETED_TESTS** | Executed against candidate | 44 executed, 44 PASS (7.28s) | **PASS** |
| **SKIPPED_COUNT** | Exactly 0 skipped tests | 0 skipped | **PASS** |
| **DIFF_CHECK** | Clean `git diff --check` | 0 trailing whitespace errors | **PASS** |
| **KNOWN_BLOCKERS** | Zero unresolved causal P0s | All P0 defects resolved | **PASS** |

**PRE_CODEX_READY:** `YES`  
**FINAL_SHA:** `9f219f187a415ffef8b6c867b2ff9c26ad0a5b88`  
**NEXT:** `CODEX_HIGH_ONCE`  

---

## 2. Exact 12-Case Acceptance Matrix (Candidate 9f219f18)

1. **Task Expected Artifact Coverage:** `PASS` (`courier_verifier.py:62-65` checks expected paths from task definition).
2. **Omission Bypass Test:** `PASS` (`test_verifier_rejects_omitted_expected_artifact` line 382 passes).
3. **Correct Server Bytes PASS:** `PASS` (`test_verifier_checks_expected_sha256` subtest 1 line 152 passes).
4. **Wrong Server Bytes FAIL:** `PASS` (`test_verifier_checks_expected_sha256` subtest 2 line 155 passes).
5. **Worker Expected Hash Rejection:** `PASS` (`test_verifier_checks_expected_sha256` subtest 4 line 163 passes; worker hash untrusted).
6. **Worker Expected Hash Omission:** `PASS` (`courier_verifier.py:78` derives expected hash strictly from task).
7. **Legacy No-Task Expectation:** `PASS` (`courier_verifier.py:80` only checks expected hash if task defines it).
8. **Malformed Target Fail-Closed:** `PASS` (`test_upload_rejects_wrong_binding_name_or_claims` line 60 passes; returns HTTP 400).
9. **Verifier Poison Pill Resilience:** `PASS` (`test_verifier_poison_pill_isolation` line 397 passes; loop catches task exceptions and continues).
10. **Result Schema Boundary:** `PASS` (`integration_contract.py:154-156` disallows `expected_sha256` in worker artifacts).
11. **Identical Replay & Reload ACK:** `PASS` (`test_resent_result_is_acknowledged_idempotently` line 68 passes).
12. **Changed Metadata Reject:** `PASS` (`test_conflicting_result_for_processed_task_is_rejected` line 70 passes; `server/app.py:367` checks 6-tuple `("dispatch_id", "result_id", "status", "worker_id", "attempt_id", "artifacts")`).

**Summary:** 12/12 PASS on Candidate `9f219f18`. All 7 prior failing cases are now fully resolved and proven.

---

## 3. Five-File Authorized Scope Audit

1. `scripts/courier_verifier.py`: Task expectation derivation + per-task loop error isolation + whitespace cleanup.
2. `scripts/integration_contract.py`: Worker artifact schema disallows `expected_sha256`.
3. `server/app.py`: Full 6-tuple duplicate check on task result intake + whitespace clean.
4. `tests/test_artifact_upload_flow.py`: Verifier task expectation, omission rejection, and poison pill isolation tests.
5. `tests/test_p3_server_idempotency.py`: Replay, conflict rejection, and retry idempotency regression tests.

`UNEXPECTED_CHANGED_FILES=0`

---

## 4. Physical Proof Prerequisite Status (Phases 3 & 4)

- **RUN_1 (A -> VERIFY -> B):** Proven on Port 8081 staging coordinator (`run1_proof.json`, `human_relay_count: 0`, `VERDICT: PASS`).
- **RUN_2 (Controlled Restart & No-Replay):** Proven on Port 8081 staging coordinator (`run2_proof.json`, `replayed: false`, `attempts: 1` preserved, `VERDICT: PASS`).
- Attestation record: `ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md`.

---

## 5. Next Step

Candidate `9f219f187a415ffef8b6c867b2ff9c26ad0a5b88` is ready for the single independent Codex review pass:  
**`NEXT=CODEX_HIGH_ONCE`**
