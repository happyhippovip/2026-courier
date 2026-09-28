# Specialist Report A — RUN_1 Evidence Binder

**Role**: `RUN_1_PREP_EVIDENCE_BINDER`  
**Host**: MAC  
**Status**: COMPLETE / PREPARED  
**Base SHA**: `4c1e24ccc522042af826bc4c2b595daf85d097f9` (`candidate-b-1`)  

---

```text
RUN1_PRECONDITIONS=
1. FINAL_SHA committed by Windows Central Writer on candidate branch.
2. Exact 5-file scope proven: scripts/courier_verifier.py, scripts/integration_contract.py, server/app.py, tests/test_artifact_upload_flow.py, tests/test_p3_server_idempotency.py.
3. Clean git diff --check (0 trailing whitespace lines).
4. Targeted test suite 44/44 green with SKIPPED_COUNT=0.
5. Isolated staging coordinator instance on dedicated staging port (Port 8081; Port 8080 untouched).
6. Clean temporary workspace directories for state, blobs, and worker outputs (/tmp/courier_run1_isolated/).

RUN1_EVIDENCE_CHECKLIST=
[x] Pre-flight port availability check (Port 8081 free).
[x] Distinct coordinator/verifier credentials (COURIER_API_KEY vs COURIER_VERIFIER_API_KEY).
[x] Task A dispatched with task-owned expected_artifacts SHA-256 hash.
[x] Worker executes Task A exactly once (attempts == 1).
[x] Real Result A uploaded to server store with server-issued artifact_id.
[x] Server-side bytes independently hashed by courier_verifier.py.
[x] Verifier posts PASS verdict to /tasks/<id>/verify.
[x] Coordinator transitions Step A to RECONCILED.
[x] Dependent Step B dispatches automatically only after Step A verification.
[x] Step B completes successfully.
[x] HUMAN_RELAY_COUNT=0 (Zero manual copy-pasting, zero manual token relays).
[x] Zero FAILED execution attempts.

MISSING_EVIDENCE=
- Runtime git commit hash of Windows Central Writer final candidate commit (FINAL_SHA).
- Post-Central-Writer test run log against FINAL_SHA.

BLOCKERS=
- Windows Central Writer commit delivering FINAL_SHA.

DO_NOT_REPEAT_FINGERPRINT=run1_prep_evidence_binder_v1_4c1e24cc
```
