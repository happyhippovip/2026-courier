# MAC-FINISH-09 — Failed Execution Quarantine Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-09
- **Area**: FAILED_EXECUTION_QUARANTINE
- **Status**: COMPLETE

Defines failure isolation, poison pill containment, and forensic quarantine protocols.

---

## 2. Failure Classification
- **Category 1 (Transient Network)**: Retry with exponential backoff (Max 1 retry).
- **Category 2 (Deterministic Verification Failure)**: Immediate quarantine, zero automatic retry.
- **Category 3 (Crash / Memory Out of Bounds)**: Immediate abort of staging run, capture heap/stack dump.

---

## 3. Quarantine Directory Specification
Failed artifacts and state dumps are quarantined into:
`server/state/quarantine/{task_id}_{timestamp}/`
- Contains:
  - `failed_state.json`
  - `captured_artifacts/`
  - `stderr.log`
  - `failure_verdict.json`
