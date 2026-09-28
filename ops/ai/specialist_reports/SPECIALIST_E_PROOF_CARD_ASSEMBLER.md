# Specialist Report E — Proof Card Assembler

**Role**: `PROOF_CARD_ASSEMBLER`  
**Host**: MAC  
**Status**: COMPLETE / PREPARED  

---

```text
PROOF_CARD_READY_FIELDS=
1. Goal-ID: goal-canary-001 (UUID format goal-[a-f0-9]{8})
2. Goal-Contract-Fingerprint: sha256_canonical_hash(goal_text, planned_steps)
3. Task-ID: task-canary-001
4. Actual Result: SUCCESS, result_id: result-canary-001, artifacts: [courier_canary_task-canary-001.txt]
5. Acceptance Criteria: Independent verifier SHA-256 hash check == task-owned expectation
6. Evidence-IDs: run1_proof.json, run2_proof.json, test_artifact_upload_flow.py, test_p3_server_idempotency.py
7. Proof Level: L4 (Physical Execution + Independent Verifier + Controlled Restart Recovery)
8. Source Fingerprint: 4c1e24ccc522042af826bc4c2b595daf85d097f9 (candidate-b-1)
9. Covered Surface: scripts/courier_verifier.py, scripts/integration_contract.py, server/app.py, server/store.py, tests/
10. UNKNOWNs: Exactly 0 gate-violating UNKNOWNs in verified surface
11. Human Interventions: Exactly 0 (HUMAN_RELAY_COUNT=0)
12. Revalidation Status: VALID_FOR_BASE_4C1E24CC; Awaiting CW FINAL_SHA

UNKNOWN_FIELDS=
- FINAL_SHA (currently PENDING_WINDOWS_CENTRAL_WRITER)
- Post-patch runtime build digest (to be minted upon CW commit)

MISSING_EVIDENCE=
- Signed FINAL_SHA commit hash from Windows Antigravity Central Writer

REVALIDATION_TRIGGERS=
- FINAL_SHA_CHANGED: Invalidation trigger for candidate-sensitive tests and physical canary hashes
```
