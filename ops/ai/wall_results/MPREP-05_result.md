# Result for MPREP-05: Restart-Matrix Open Cells

TASK=MPREP-05
STATUS=PASS
RESULTS_REUSED=ops/ai/coordination_reports/FAMILY_07_RESTART_MATRIX_A4.md, ops/ai/coordination_reports/FAMILY_06_RUN_2_RESTART_RESILIENCE.md, ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md (PHYS-003)
OUTPUT=Restart-Matrix Status Mapping (Focus: OPEN / BLOCKED Cells for Muse):
- **Scenario 1 (Coordinator Restart Mid-Goal)**: `PROVEN_ON_BASE` via PHYS-003 on Port 8081 (`run2-task-a` attempts=1, zero replay, Step B auto-dispatched). `OPEN` for re-verification on FINAL_SHA.
- **Scenario 2 (Worker Disappears / Unresponsive)**: `PROVEN` via `tests/test_server_integration_contract.py` (quarantined without blind replay).
- **Scenario 3 (Result Persisted / Reconcile Missing)**: `PROVEN` via `tests/test_artifact_upload_flow.py` (poller picks up pending task independently).
- **Scenario 4 (READY Before Dispatch Concurrency)**: `PROVEN` via `tests/test_server_integration_contract.py` (exactly one winner).
- **Scenario 5 (Dispatch Happened / Result Missing)**: `PROVEN` via `tests/test_p3_server_idempotency.py` (lease expiration / operator resume).
- **Scenario 6 (Temporary Provider / Network Failure)**: `PROVEN` via `tests/test_artifact_upload_flow.py` (upload retries without command re-execution).
- **Scenario 7 (Stale Result Arrival)**: `PROVEN` via `tests/test_result_identity_binding.py` (superseded attempts fail closed).
- **Scenario 8 (Identical Duplicate Result)**: `BLOCKED_ON_CW` (`server/app.py:367` duplicate comparison omits `worker_id` and `attempt_id`).
- **Scenario 9 (Conflicting Duplicate Result)**: `PROVEN` via `tests/test_p3_server_idempotency.py` (HTTP 409 Conflict).

**Summary of OPEN / BLOCKED Cells for Muse**:
1. `CELL-S8`: Scenario 8 Duplicate Equivalence (`server/app.py:367`) — BLOCKED on Central Writer patch.
2. `CELL-S1-FINAL`: Scenario 1 Physical Restart Gate Re-run — OPEN on FINAL_SHA publication.
MISSING=Central Writer patch for `server/app.py:367` to turn CELL-S8 to PROVEN.
BLOCKER=Windows Central Writer commit.
MUSE_INPUT=Muse 02:00 should independently verify CELL-S8 once Windows CW incorporates Defect 3.
DO_NOT_REPEAT_FINGERPRINT=mprep-05-restart-matrix-open-cells-v1

DO_NOT_REPEAT_FINGERPRINT=sha256-33571e10780cc2f9
