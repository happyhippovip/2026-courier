# Specialist Report D — Restart Matrix Closer

**Role**: `RESTART_MATRIX_CLOSER`  
**Host**: MAC  
**Status**: COMPLETE / AUDITED  

---

### 1. Courier Process Restart
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md` (Phase 4), `tests/test_p3_server_idempotency.py:100-109`
- **MISSING**: None
- **NEXT_SMALLEST_CHECK**: Re-run on FINAL_SHA after Windows CW commit.

### 2. Worker Disappears (Process Crash / Offline)
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `server/app.py:270-275`, `tests/test_p3_server_idempotency.py:111-126`, `FAMILY_16_PILOT_FAILURE_MODES.md`
- **MISSING**: None (300s lease expiry and unregister recovery proven)
- **NEXT_SMALLEST_CHECK**: None.

### 3. Result Persisted, Reconcile Missing
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `server/app.py:382-384`, `server/app.py:430-445`, `FAMILY_07_RESTART_MATRIX_A4.md`
- **MISSING**: None (Task remains in RESULT_RECEIVED; verifier re-polls on boot)
- **NEXT_SMALLEST_CHECK**: None.

### 4. READY Before Dispatch
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `server/app.py:280-285`, `tests/test_p3_server_idempotency.py:20-27`
- **MISSING**: None (Task remains QUEUED in state JSON)
- **NEXT_SMALLEST_CHECK**: None.

### 5. Dispatch Occurred, Result Missing
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `server/app.py:313,388`, `FAMILY_07_RESTART_MATRIX_A4.md`
- **MISSING**: None (Lease expires after 300s, enabling retry or HUMAN_REQUIRED)
- **NEXT_SMALLEST_CHECK**: None.

### 6. Provider Temporarily Unavailable (429 / 503)
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `FAMILY_16_PILOT_FAILURE_MODES.md`, `FAMILY_10_COST_RESOURCE_SAFETY.md`
- **MISSING**: None (Exponential backoff 3 retries; task state preserved in ARBEITET)
- **NEXT_SMALLEST_CHECK**: None.

### 7. Stale Result (Late Result from Prior Attempt)
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `tests/test_p3_server_idempotency.py:64`, `scripts/integration_contract.py:139-140`
- **MISSING**: None (Rejected with HTTP 400 ContractError attempt_id mismatch)
- **NEXT_SMALLEST_CHECK**: None.

### 8. Identical Duplicate Result (Network Replay)
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `tests/test_p3_server_idempotency.py:84-90`, `server/app.py:366-368`
- **MISSING**: Central Writer fix expanding duplicate check tuple to include worker_id/attempt_id (P0 Defect 3)
- **NEXT_SMALLEST_CHECK**: Verify expanded tuple against FINAL_SHA.

### 9. Contradictory Duplicate Result (Mismatched Payload)
- **STATUS**: PROVEN
- **EVIDENCE_REF**: `tests/test_p3_server_idempotency.py:92-98`, `server/app.py:369-371`
- **MISSING**: None (Rejected with HTTP 409 Conflict)
- **NEXT_SMALLEST_CHECK**: None.
```
