# SOURCE CODE MAP: COURIER 2026 ARCHITECTURE

**MISSION ID**: `WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2`  
**PHASE**: `PHASE A — REAL SOURCE CARTOGRAPHY`  
**STATUS**: `VERIFIED AGAINST CURRENT PRODUCTION TREE`  

---

## 1. CORE PRODUCTION MODULE CARTOGRAPHY

### 1.1 `supervisor/lease_manager.js`
- **Path**: `courier/supervisor/lease_manager.js`
- **Purpose**: Durable Process Ownership, PID Fingerprinting & Parent-Child Task Lifecycle Management.
- **Entry Points**: `createLease()`, `recordHeartbeat()`, `updateStatus()`, `reconcileChildrenOnParentCompletion()`, `getActiveLeasesForMachine()`.
- **Writes**: `runtime/leases/leases.json` (atomic write via `.tmp` rename).
- **Reads**: `runtime/leases/leases.json`.
- **State Ownership**: Process Lease records, PID attribution, machine ID binding, heartbeat nonces.
- **Dependencies**: `supervisor/types.js`, `crypto`, `fs`, `path`.
- **Failure Modes**:
  - PID recycling on Windows where a dead process PID is reallocated to an unrelated system process.
  - Heartbeat stall detection race condition.
  - JSON parse errors if concurrent non-atomic writes touch `leases.json`.
- **Existing Tests**: `tests/test_supervisor_plane_p0.js`.
- **Missing Tests / Gaps**: Cross-machine lease conflicts; power-loss truncation recovery; multi-process lease race.

---

### 1.2 `supervisor/no_stacking.js`
- **Path**: `courier/supervisor/no_stacking.js`
- **Purpose**: Enforces No-Stacking invariant for equivalent heavy work on the same machine.
- **Entry Points**: `evaluateHeavyTaskSubmission()`, `computeTaskWorkSignature()`.
- **Writes**: None (read-only decision engine).
- **Reads**: Queries `ProcessLeaseManager.getActiveLeasesForMachine()`.
- **State Ownership**: None (stateless evaluator over active leases).
- **Dependencies**: `supervisor/types.js`, `crypto`.
- **Failure Modes**:
  - Hierarchical parent/child directory collisions (e.g. `repo/src` vs `repo/`) not caught by simple command string comparison.
  - Case-insensitivity and path separator normalization bypasses (`..`, `\`, `/`).
- **Existing Tests**: `tests/test_supervisor_plane_p0.js`.
- **Missing Tests / Gaps**: Symlink/junction resolution collisions; overlapping scope definitions.

---

### 1.3 `supervisor/reconciliation.js`
- **Path**: `courier/supervisor/reconciliation.js`
- **Purpose**: Crash and restart reconciler. Classifies live, missing, and orphan tasks; enforces `EXECUTION_UNCERTAIN`.
- **Entry Points**: `reconcile({ livePids, liveProcessMap, pendingDispatchTasks })`.
- **Writes**: Mutates lease status in `ProcessLeaseManager` and records audit events in `auditLedger`.
- **Reads**: Inspects all leases in `ProcessLeaseManager`.
- **State Ownership**: Post-crash state reconciliation decisions.
- **Dependencies**: `supervisor/types.js`.
- **Failure Modes**:
  - Automatic redispatch of uncertain tasks without proof of effect/non-effect.
  - Blindly killing unknown live processes instead of treating as `UNATTRIBUTED_NEVER_BLINDLY_KILL`.
- **Existing Tests**: `tests/test_supervisor_plane_p0.js`.
- **Missing Tests / Gaps**: Multiple sequential crashes during reconciliation; corrupted lease files during restart.

---

### 1.4 `supervisor/resource_governor.js`
- **Path**: `courier/supervisor/resource_governor.js`
- **Purpose**: Machine-local resource governor. Tracks memory, CPU, thermal pressure, and enforces concurrency ceilings.
- **Entry Points**: `evaluateAdmission()`, `updateMachineState()`, `recordResourceMetric()`.
- **Writes**: Machine state cache and audit logs.
- **Reads**: OS metrics and current lease counts.
- **State Ownership**: Host concurrency allocations (`MAC: 1 heavy`, `WINDOWS: 4 heavy`).
- **Dependencies**: `supervisor/types.js`.
- **Failure Modes**:
  - Memory leak in metric recording.
  - Unbounded task queuing when host enters sustained pressure.
- **Existing Tests**: `tests/test_supervisor_plane_p0.js`.
- **Missing Tests / Gaps**: Adaptive priority-based shed under acute memory exhaustion.

---

### 1.5 `supervisor/audit_ledger.js`
- **Path**: `courier/supervisor/audit_ledger.js`
- **Purpose**: Append-only JSONL event log of all supervisor state transitions.
- **Entry Points**: `recordEvent()`, `getEventsForTask()`, `getAllEvents()`.
- **Writes**: `runtime/audit/audit_events.jsonl`.
- **Reads**: `runtime/audit/audit_events.jsonl`.
- **State Ownership**: Historical supervisor event log.
- **Dependencies**: `fs`, `path`, `crypto`.
- **Failure Modes**:
  - Partial line writes on sudden process termination.
  - Silent file truncation.
- **Existing Tests**: `tests/test_supervisor_plane_p0.js`.
- **Missing Tests / Gaps**: Cryptographic hash chaining verification; compaction/archival recovery.

---

### 1.6 `money_factory/safety_gates.js`
- **Path**: `courier/money_factory/safety_gates.js`
- **Purpose**: Hard-coded financial safety barriers: `AUTONOMOUS_SPEND_LIMIT_EUR = 0`, `REAL_TRADES = 0`.
- **Entry Points**: `checkOperation()`, `createSpendRequest()`, `executeSpend()`, `executeTrade()`, `signWithWallet()`.
- **Writes**: Generates immutable spend request manifests requiring human signature.
- **Reads**: Invariant constants.
- **State Ownership**: Economic safety invariants.
- **Dependencies**: `crypto`.
- **Failure Modes**:
  - Deferred liabilities (auto-renewing free trials) bypassing immediate spend checks.
  - Downgrade of human gate category by worker task descriptors.
- **Existing Tests**: `tests/test_money_factory_p0.js`, `tests/test_money_factory_closure.js`.
- **Missing Tests / Gaps**: Single-use token replay prevention; scope-bound cryptographic token verification.

---

### 1.7 `money_factory/anti_loop_policy.js`
- **Path**: `courier/money_factory/anti_loop_policy.js`
- **Purpose**: Detects and prevents endless looping over identical unviable opportunities.
- **Entry Points**: `evaluateLoopRisk()`, `recordAttempt()`.
- **Writes**: Loop counter state.
- **Reads**: Historical attempts.
- **State Ownership**: Attempt counters per opportunity ID.
- **Dependencies**: None.
- **Failure Modes**:
  - Reset of loop counters on process restart.
  - Alias opportunities evading loop detection via minor title alterations.
- **Existing Tests**: `tests/test_money_factory_p0.js`.
- **Missing Tests / Gaps**: Content-hash deduplication across distinct opportunity IDs.

---

### 1.8 `chief/control_plane.py` & `chief/coordinator.py`
- **Path**: `courier/chief/control_plane.py`, `courier/chief/coordinator.py`
- **Purpose**: Top-level mission coordination and cross-device dispatch orchestration.
- **Entry Points**: `dispatch()`, `sync()`, `reconcile()`.
- **Writes**: Cross-device state manifests.
- **Reads**: Worker task completion reports.
- **State Ownership**: Global mission progression state.
- **Dependencies**: `safewrite.py`, `delta_engine.py`, `validator.py`.
- **Failure Modes**:
  - Split-brain between Windows and Mac coordinators.
  - Stale status reporting due to delayed ingestion.
- **Existing Tests**: `tests/test_cross_device_intake.py`.
- **Missing Tests / Gaps**: Asynchronous message reordering; duplicate task result races.
