# POST-FREEZE INTEGRATION MAP — COURIER RC3 HARDENING LAB

> **SAFETY MANDATE**: This document identifies future integration candidates and integration points for the Mac host. **NO INTEGRATION IS EXECUTED** during this lab session. The frozen release `COURIER_HANDOFF_RC3` and all active Mac lifecycles remain completely untouched.

---

## 1. COMPONENT CLASSIFICATION MATRIX

| Component / Subsystem | Primary Source Module | Classification | Target Integration Point | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Task Stamp Contract Model** | `scratch/rc3_hardening_lab/task_stamp_contract.js` | `READY_TO_INTEGRATE` | `supervisor/task_coordinator.js` | WP5 (8/8), WP10 (12/12), WP12 (100/100) |
| **Worker Lease & Scope Exclusivity** | `task_stamp_contract.js` (`acquireWriterLease`) | `READY_TO_INTEGRATE` | `supervisor/worker_pool.js` (dispatch gate) | WP5 (8/8), WP10 (12/12), WP12 (100/100) |
| **Process Lease Manager** | `supervisor/process_lease.js` | `READY_TO_INTEGRATE` | `supervisor/process_lease.js` | WP3 (21/21), Baseline P0 (45/45) |
| **Follow-Up Inbox** | `scratch/rc3_hardening_lab/follow_up_inbox.js` | `READY_TO_INTEGRATE` | `supervisor/follow_up_inbox.js` | WP6 (7/7), WP11 (9/9), WP12 (100/100) |
| **Border Guard Contract** | `scratch/rc3_hardening_lab/border_guard_contract.js` | `READY_TO_INTEGRATE` | `supervisor/border_guard.js` (pre-dispatch) | WP7 (11/11), WP12 (100/100) |
| **Result Customs Contract** | `scratch/rc3_hardening_lab/result_customs_contract.js` | `READY_TO_INTEGRATE` | `supervisor/result_customs.js` (post-execution) | WP8 (15/15), WP10 (12/12), WP12 (100/100) |
| **Resource / Thermal Governor** | `supervisor/resource_governor.js` | `NEEDS_MAC_NATIVE_PROOF` | `supervisor/resource_governor.js` | WP4 (12/12), Baseline P0 (45/45) |
| **Crash Reconciliation / Idempotency** | `task_stamp_contract.js` + `audit_ledger.js` | `READY_TO_INTEGRATE` | Supervisor cold boot initialization sequence | WP10 (12/12), WP11 (9/9), WP12 (100/100) |
| **Evidence Ledger Duplicate Settlement & Validation** | `money_factory/evidence_ledger.js` | `READY_TO_INTEGRATE` | `money_factory/evidence_ledger.js` | WP9 (19/19), WP14 (18/18, 13/13) |
| **Prediction Calibration Immutability** | `money_factory/prediction_calibration.js` | `READY_TO_INTEGRATE` | `money_factory/prediction_calibration.js` | WP9 (19/19), WP14 (18/18, 13/13) |
| **JSONL Per-Line Recovery & Newline Safeguards** | Ledgers (`audit_ledger.js`, `evidence_ledger.js`) | `READY_TO_INTEGRATE` | All JSONL storage loaders & appenders | WP11 (9/9), WP12 (100/100) |
| **Intake Validator Physical Tree Traversal** | `tests/rc3_hardening/test_rc3_adversarial_validation.js` | `READY_TO_INTEGRATE` | Mac `validate_handoff_rc3.sh` | WP2 (25/25 fail-closed) |
| **Multi-Currency External Settlement Handlers** | Money Factory Settlement adapters | `NEEDS_CODEX_REVIEW` | External payment settlement ingestion | WP9 Invariant: `REAL_REVENUE_EUR = 0` |
| **Autonomous Spend / Real Trading** | N/A (Disallowed) | `DO_NOT_INTEGRATE` | N/A | Hard Safety Invariant |
| **Automated Human Gate Bypass** | N/A (Disallowed) | `DO_NOT_INTEGRATE` | N/A | Hard Safety Invariant |
| **Legacy Ad-hoc File Lockfiles** | N/A (Replaced) | `SUPERSEDED` | N/A | Superseded by Task Stamp Leases |

---

## 2. DETAILED INTEGRATION SPECIFICATIONS

### A. Task Stamp & Worker Lease (`READY_TO_INTEGRATE`)
- **Objective**: Eliminate task stacking and race conditions by strictly gating dispatches behind exclusive scope leases.
- **Contract**:
  - Exactly one active writer lease per intersecting scope path.
  - Second writer requesting intersecting scope path is placed on `HOLD` (never fails silently, never concurrent write).
  - Tasks cannot be dispatched until `STAMPED` with SHA256 task fingerprint.
  - Task definitions become immutable once `STAMPED`.
  - State machine strictly monotonic: `PROPOSED` -> `NEGOTIATING` -> `APPROVED_FOR_DISPATCH` -> `STAMPED` -> `DISPATCHED` -> `IN_FLIGHT` -> `RESULT_RECEIVED` -> `VERIFIED` -> `CLOSED`.

### B. Follow-Up Inbox (`READY_TO_INTEGRATE`)
- **Objective**: Allow user, supervisor, or workers to log ideas, bugs, and optimizations during task execution without disrupting active workers.
- **Contract**:
  - Append-only JSONL storage (`follow_up_inbox.jsonl`).
  - 11 canonical fields; 8 canonical statuses.
  - Workers in-flight cannot be interrupted by new ideas; ideas are captured and held for subsequent planning turns.
  - Duplicate thoughts indexed by `sha256(goal_id:norm_thought)`.

### C. Border Guard (`READY_TO_INTEGRATE`)
- **Objective**: Protect outbound dispatches against accidental destructive actions and enforce strict safety boundaries.
- **Contract**:
  - Fail-closed blocking of financial spend, production deploy, public publishing, external messaging, and crypto/trading.
  - Outbound decision enum: `GREEN_CARD`, `REVISE`, `HOLD`, `BLOCK`, `ESCALATE`.
  - Bounded appeal: Exactly 1 appeal allowed per task to prevent infinite coordinator/worker rebuttal loops.

### D. Result Customs (`READY_TO_INTEGRATE`)
- **Objective**: Inbound qualification of worker execution results.
- **Contract**:
  - Validates 42 standard result envelope fields.
  - Cryptographic verification of result fingerprint and artifact hashes.
  - Mandatory evidence validation: if `TESTS_RUN > 0`, `TEST_COMMANDS` and `LOG_PATHS` must be present.
  - Replay protection: duplicates rejected.
  - Goal authority restriction: Result Customs never declares an entire goal `SATISFIED`.

### E. Resource Governor (`NEEDS_MAC_NATIVE_PROOF`)
- **Objective**: Throttle worker spawning when system resources are exhausted.
- **Repair**: Added `swap_pressure === 'HIGH'` to `PRESSURE` state triggers.
- **Mac Host Action**: Before integrating into the Mac Courier, verify telemetry collection commands (`sysctl vm.swapusage`, `powermetrics` or `pmset -g therm`) on the actual macOS hardware.

### F. Money Factory Hardening (`READY_TO_INTEGRATE`)
- **Objective**: Ensure absolute auditability and immutability of revenue claims and model calibrations.
- **Contract**:
  - `claim_value_eur` strictly positive numeric.
  - Duplicate settlement receipts idempotently rejected (`DEFECT-WP9-002`).
  - Prediction calibration resolutions immutable (`DEFECT-WP9-003`).
  - Verified invariant: `REAL_REVENUE_EUR = 0` holds across all synthetic, simulated, and projection workflows.

---

## 3. STRICT BOUNDARIES
- Frozen release `COURIER_HANDOFF_RC3` was NOT modified.
- No files on the Mac host were touched.
- No git commits, pushes, or deployments were performed.
- All repairs were verified within the Windows hardening lab with 315/315 tests passing.
