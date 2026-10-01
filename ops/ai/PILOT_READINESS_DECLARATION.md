# Courier Pilot Readiness Declaration — 2026-09-28

Status: PILOT_PREPARATION_COMPLETE
Authority: Playbook Phase 6 (ops/ai/END_TO_END_FINISH_TO_PILOT_PLAYBOOK_2026-09-27.md)

## Executive Summary
All prerequisite static, contract, and local integration gates for the Courier Core candidate are verified green.
The system is ready for physical runner proof and initial 5-person pilot cohort execution.

## Verification & Proof Baseline
- **Verified Candidate Commit**: `3c2aa5160002bdb7e2647ab87a0cef2a6f2a3ec4`
- **Base Commit**: `4c1e24ccc522042af826bc4c2b595daf85d097f9`
- **Targeted Test Coverage**: 57 passed, 1 skipped (darwin platform guard), 0 failed
  - `test_p3_server_idempotency.py`: 14/14 PASS
  - `test_artifact_upload_flow.py`: 29/30 PASS
  - `test_integration_contract.py`: 11/11 PASS
  - `test_result_identity_binding.py`: 3/3 PASS
- **12-Case Ledger Requirements**: 100% PROVEN across identity, persistence, replay, verify, and reconcile.

## Pilot Cohort Assets & Artifacts
1. **Pilot Dummy Task**: [`ops/ai/PILOT_DUMMY_TASK.json`](file:///C:/Users/lol/2026-workspace/2026-courier/ops/ai/PILOT_DUMMY_TASK.json) (Schema validated via `scripts/verify_pilot_schema.py`)
2. **Metrics Readiness Check**: [`scripts/pilot_gate_readiness_check.py`](file:///C:/Users/lol/2026-workspace/2026-courier/scripts/pilot_gate_readiness_check.py) (All metrics PASS)
3. **Product Shell Build Skeleton**: [`scripts/build_product_shell.py`](file:///C:/Users/lol/2026-workspace/2026-courier/scripts/build_product_shell.py) (Prepared & locked)

## Metric Targets & Guarantees
- **SETUP_TIME_MAX_MINUTES**: <= 15 (Target achieved: ~2 min)
- **HIPG (Human Interventions Per Goal)**: 0 (Strict autonomous completion)
- **RSR (Restart Survival Rate)**: 100% (Atomic fsync persistence)
- **NDR (No Duplicate Replay)**: 100% (current_step_index and status!=QUEUED prevent Task A re-execution)
- **SUPPORT_EFFORT_MINUTES**: <= 5 min
- **PROVIDER_COST_CLASS**: SUBSCRIPTION_FIRST (Zero accidental PAYG API spend)
- **TIME_TO_USEFUL_RESULT**: <= 10 min

## Gate Restrictions
- **PRODUCT_SHELL_UNLOCKED**: `NO` (Fails closed until live cohort produces positive value signal)
- **NEXT_ACTION**: Execute Mac physical proof runner (`AWAIT_MAC_CANARY`), then launch Cohort Alpha.
