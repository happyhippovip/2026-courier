# POST-FREEZE INTEGRATION PLAN — COURIER INVARIANTS A01, L01, G01, B01

- **Mission**: `WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1`
- **Target Branch Post-Freeze**: Mainline Courier (after active Mac lifecycle freeze)
- **Executive Summary**: This document specifies the complete, red-team-hardened engineering plan to integrate the four validated invariants into the Courier production codebase without risking regressions, deadlocks, or security loopholes.

---

## 1. INTEGRATION OBJECTIVES & BOUNDARIES
1. **Zero Downtime / Zero Data Loss**: Existing active tasks and durable historical ledgers must transition smoothly without loss of context or task corruption.
2. **Monotonically Increasing Safety**: Each incremental stage must strictly enhance safety without opening transitional attack windows.
3. **Strict Separation of Concerns**:
   - `A01` belongs in the central **Dispatcher** (`core/dispatcher.js`).
   - `L01` belongs in the **Resource/Lease Manager** (`supervisor/resource_lock_manager.js` & `supervisor/lease_manager.js`).
   - `G01` belongs in the **Safety Gate & Capability Interceptor** (`money_factory/safety_gates.js` & tool gateway).
   - `B01` belongs in the **Process Adapter & Reconciler** (`supervisor/process_identity.js` & `supervisor/reconciliation.js`).

---

## 2. STAGED INTEGRATION ROADMAP

```text
STAGE 1: A01 Dispatcher Uncertainty Fence
  ├── Prerequisites: None (self-contained)
  ├── Verification: 14/14 indirect dispatch paths fail closed
  └── Rollback Point: Single boolean bypass in Dispatcher

STAGE 2: L01 Hierarchical & Semantic Resource Locks
  ├── Prerequisites: Stage 1 active
  ├── Verification: Parent/child, case-folding, and non-fs collisions blocked
  └── Rollback Point: Fallback to exact string equality in lease check

STAGE 3: G01 Deferred Liability & Capability Gate
  ├── Prerequisites: Stage 1 active (Uncertainty fence protects financial retry)
  ├── Verification: Zero false negatives on auto-renew/deferred commitments
  └── Rollback Point: Fallback to static verb array check

STAGE 4: B01 Multi-Factor Process Identity (Darwin Mac Native)
  ├── Prerequisites: Mac lifecycle frozen; Darwin proc_pidinfo verified on hardware
  ├── Verification: Zero false liveness matches during rapid PID recycling
  └── Rollback Point: Fail-closed UNKNOWN policy preserved
```

---

## 3. COMPONENT IMPLEMENTATION DETAILS

### Stage 1: Candidate A01 (Execution-Uncertainty Fence)
- **Target File**: `courier/core/dispatcher.js` (and `supervisor/index.js`)
- **Action**: Wrap the task dispatch entry point with `DispatcherUncertaintyFence.assertDispatchPermitted(task, context)`.
- **Key Test**: Inject `task.state = 'EXECUTION_UNCERTAIN'` and trigger all 14 callers (Router, Governor reroute, Hygiene requeue, etc.). All 14 must receive `SecurityBoundaryViolation` and fail closed.

### Stage 2: Candidate L01 (Hierarchical Scope Locks)
- **Target Files**: `courier/supervisor/resource_lock_manager.js` (NEW), `courier/supervisor/lease_manager.js` (MODIFY).
- **Action**: Add `declared_resources` to `createLease()`. Before lease acquisition, verify cross-resource conflicts using hierarchical prefix logic with trailing slash and platform case normalization.
- **Key Test**: Concurrent dispatch of `tree:src/` and `tree:src/core/auth/` must serialize; concurrent dispatch of `tree:src/moduleA/` and `tree:src/moduleB/` must run in parallel.

### Stage 3: Candidate G01 (Deferred Liability & Capability Gate)
- **Target Files**: `courier/money_factory/safety_gates.js` (MODIFY), `courier/core/tool_runner.js` (MODIFY).
- **Action**: Introduce `HardenedSafetyGate.evaluateIntent()` parsing deferred commitments (`auto-renew`, `free trial`, `billing agreement`) and intercepting financial tool capabilities (`stripe_charge`, etc.). Enforce single-use approval token verification.
- **Key Test**: Prompts with "free trial with auto-renew at €50/mo" must halt with `HUMAN_GATE_REQUIRED`; prompts with "analyze deployment plan" must pass autonomously.

### Stage 4: Candidate B01 (Multi-Factor Process Identity)
- **Target Files**: `courier/supervisor/process_identity.js` (NEW), `courier/supervisor/reconciliation.js` (MODIFY).
- **Action**: Add `process_start_time_epoch_ms` and `task_token` to lease schema. Update reconciler to require multi-factor match before asserting liveness or issuing SIGKILL.
- **Key Test**: Spawn worker, kill it, immediately spawn dummy process with recycled PID; verify reconciler flags `DEFINITE_MISMATCH` or `UNKNOWN` and never kills the dummy process.

---

## 4. NON-GOALS & INTENTIONAL LIMITATIONS
- No invasive OS GUI automation or screenshot-driven decision loops.
- No remote cloud orchestration or external webhooks during local supervision.
- No automated sudo or privilege escalation.
- No alteration of the hard-coded invariant: `AUTONOMOUS_SPEND_LIMIT_EUR = 0`.
