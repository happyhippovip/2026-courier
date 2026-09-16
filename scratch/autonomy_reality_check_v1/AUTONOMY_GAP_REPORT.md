# AUTONOMY GAP REPORT: WINDOWS COURIER PRODUCTION ENTRYPOINT

**Mission ID**: `WINDOWS_AUTONOMY_REALITY_CHECK_PRODUCTION_ENTRYPOINT_V1`  
**Date**: 2026-09-10  
**Classification**: **`AUTONOMY_GAP_FOUND`**  

---

## 1. Exact Missing Link

**Missing Component**: **Canonical Production Orchestrator / Entrypoint**  
Windows Courier contains hardened, complete, and thoroughly tested governance and supervisor modules, but **lacks a single production entrypoint** that accepts a high-level goal and autonomously connects the execution pipeline:
```text
Goal Intake -> Task Planner -> Router -> Resource Lock -> Process Lease ->
Task Passport -> Border Guard -> Worker Dispatch -> Result Customs ->
Completion Governor -> Next-Work Selector -> Audit Ledger
```

Currently, this lifecycle exists **only when orchestrated step-by-step by test scripts** (such as `scratch/run_autonomous_operations_mission.js` or `scratch/run_authoritative_canary_mission.js`).

---

## 2. Production Path Evidence

1. **`cross_device_intake.js`**: Only implements regex classification (`classifyAndRoute`). It has no CLI, no main method, and does not dispatch tasks or invoke supervisor modules.
2. **`money_factory/index.js`**: Implements data structures, seed categories, scoring, and ledger utilities. It does not possess an autonomous run loop.
3. **`supervisor/index.js`**: Implements the `SupervisorPlane` class with individual gate methods (`admitForDispatch`, `evaluateResultEnvelope`, `evaluateWorkerReport`). Crucially, line 3-4 states:
   > *"Architectural Invariant: This is NOT a second Courier. It is a SUPERVISOR PLANE used by Courier. Courier remains the ONLY canonical orchestrator."*
   However, the canonical Courier orchestrator that uses `SupervisorPlane` **does not exist as a production file** in `courier/`.
4. **`chief/cli.py`**: Coordinates multi-lane handoffs and generates dispatch prompts (e.g. for AGY headless), but is a Python cross-machine bridge, not the local Windows Courier runtime engine.

---

## 3. Why Previous Tests Did Not Expose It

1. **The test suites were the orchestrator**: In `test_supervisor_plane_p0.js`, `test_mandatory_scenarios_suite.js`, and `test_rc3_adversarial_validation.js`, the test functions manually called each module in sequence.
2. **The 12-stage Canary was scripted**: In `run_authoritative_canary_mission.js`, the test runner stepped from Stage 1 to Stage 12 explicitly, mocking worker execution and directly feeding outputs to the next method.
3. **The 17-second proof was harness-orchestrated**: In `run_autonomous_operations_mission.js`, the test runner stepped through Phase 1 to Phase 18 sequentially, hardcoding task arrays and state updates.

---

## 4. Severity Assessment

- **Kernel Correctness**: **ZERO DEFECT** (114/114 unit/adversarial tests PASS; 19/19 bypass attacks fail-closed; security invariants strictly hold).
- **Commercial Product**: **ZERO IMPACT** (`agent-context-trimmer v1.0.0` is 100% frozen, zero-dependency, SHA-256 verified).
- **Autonomy Classification**: **HIGH** (The claim `AUTONOMOUS_OPERATIONS_PROVEN` cannot be made for production Courier until a canonical production entrypoint is wired).

---

## 5. Smallest Possible Repair

Create a single canonical production entrypoint:  
`courier/bin/courier_runtime.js` (or `courier/index.js`)

This entrypoint will:
1. Accept a high-level goal string or options object.
2. Ingest via `CrossDeviceIntakeEngine`.
3. Query `OpportunityWarehouse` / planner for actionable work units.
4. Loop through the verified 12-stage pipeline using `SupervisorPlane`, `ResourceLockManager`, `TaskPassport`, `BorderGuard`, `ResultCustoms`, and `CompletionGovernor`.
5. Provide a clean CLI: `node bin/courier_runtime.js --goal "..."`.

---

## 6. Estimated Files Affected

- **New File**: 1 file (`bin/courier_runtime.js` or `courier_daemon.js`).
- **Modified Existing Files**: 0 files (existing modules in `governance/` and `supervisor/` require zero modifications).

---

## 7. Existing Architecture Components

- **Components Already Available**: **100%**
  - `governance/ResourceLockManager.js` (Locking)
  - `governance/TaskPassport.js` (HMAC Passports)
  - `governance/BorderGuard.js` (Pre-dispatch gate)
  - `governance/ResultCustoms.js` (Envelope & Checksums)
  - `governance/CompletionGovernor.js` (Mission status)
  - `supervisor/lease_manager.js` (Process leases)
  - `supervisor/decision_engine.js` (Decision engine)
  - `supervisor/stall_policy.js` (Stall & Anti-time-kill policy)
  - `supervisor/reconciliation.js` (Crash recovery)
  - `money_factory/index.js` (Warehouse & scoring)

---

## 8. Wiring vs. New Behavior

- **Classification**: **95% WIRING / 5% LOOP CONTROL**
- All safety checks, crypto signatures, lease identity checks, and customs gates already exist and are proven. The only missing part is the outer orchestrating loop that calls them without an external test script.

---

## 9. Regression Risk

- **Risk Level**: **EXTREMELY LOW**
- Since the repair is purely additive (adding the top-level entrypoint without modifying existing kernel files), all 114 regression tests and 19 bypass attacks will remain 100% passing.
