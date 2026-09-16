# ARCHITECTURE GAP MAP

**MISSION ID**: `WINDOWS_AUTONOMOUS_DEEP_BUILD_PROOF_FACTORY_V2`  

---

## 1. PRODUCTION REALITY VS. VERIFIED SHADOW INVARIANTS

| Subsystem | Current Production State | Shadow Model Invariant | Severity / Risk |
|---|---|---|---|
| **Dispatch & Retry** | Indirect retry paths (Supervisor, Reconciler) can redispatch without central uncertainty check | Centralized `DispatcherUncertaintyFence` dominating all 12 trigger families | **P0 (CRITICAL)** |
| **Resource Concurrency** | Basic filename-based locking; vulnerable to parent/child path clobber and symlink bypass | Canonical path prefix locking with hierarchical locks & cryptographic nonces | **P0 (CRITICAL)** |
| **Financial Safety** | Immediate spend checks exist; deferred liabilities & trial subscriptions un-fenced | Multi-phase `ZeroSpendBoundaryGovernor` checking immediate, deferred, and auto-renew flags | **P0 (CRITICAL)** |
| **Process Termination** | Direct `process.kill(pid)` without verifying start-time or process token | Tri-state process oracle (`MATCH`, `MISMATCH`, `UNKNOWN`); never kill on `UNKNOWN` | **P0 (CRITICAL)** |
| **Goal Satisfaction** | Worker exit code 0 or self-reported "DONE" accepted without deliverable hash audit | Cryptographic `GoalSatisfactionEnvelope` independently verifying file hashes & assertions | **P1 (HIGH)** |
| **Cross-Task Deadlock** | No directed wait-for graph cycle detection; circular waits cause silent hangs | `DependencyCycleAndDeadlockResolver` detecting cycles and preempting lowest priority task | **P1 (HIGH)** |
| **Result Customs** | Basic git status check; vulnerable to TOCTOU branch switch or test assertion weakening | Dual-plane `BorderGuard` + `ResultCustoms` with AST-based test weakening detection | **P1 (HIGH)** |
| **Telemetry & Alerts** | Flapping errors produce alert storms and operator fatigue | `HighSignalNotificationReducer` deduplicating within cooldown window | **P2 (MEDIUM)** |
| **Multi-Step Rollback** | Partial failures leave intermediate mutations on disk | `AtomicRollbackEngine` executing strict LIFO compensating actions from pre-state snapshots | **P1 (HIGH)** |
