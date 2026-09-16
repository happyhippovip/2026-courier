# ARCHITECTURE GAP MAP: 8-HOUR NIGHT RESEARCH FACTORY

**Mission ID**: `WINDOWS_COURIER_8H_AUTONOMOUS_NIGHT_FACTORY_V1`  
**Focus**: Structural Defect Analysis, Compositional Vulnerabilities, and Autonomy Boundaries  

---

## 1. Differential Analysis: Production vs Shadow Invariants

| Gap ID | Subsystem | Production Reality | Shadow Architectural Invariant | Severity | Target Attack Workstream |
|---|---|---|---|---|---|
| **GAP-A01** | Supervisor / Reconciler / Dispatcher | Supervisor and Reconciler retry paths can spawn fallback workers or redispatch tasks without consulting the central execution-uncertainty fence, allowing duplicated side effects if original worker is slow or unreachable. | A single execution-uncertainty fence must strictly dominate ALL 12 dispatch/retry/fallback/reroute triggers, indexed by both task_id and logical_work_id. | **P0** | REQUIRES_COMPOSITIONAL_ATTACK |
| **GAP-L01** | Supervisor / No-Stacking | Production no_stacking checks exact string equality of workspace paths. Ignores parent/child containment (e.g. locking courier/ vs courier/scratch/), Windows case-folding (courier vs COURIER), trailing slashes, and relative dot segments. | Hybrid resource lock manager resolving canonical paths, verifying prefix/containment trees, and enforcing shared/exclusive lock hierarchies. | **P0** | REQUIRES_COMPOSITIONAL_ATTACK |
| **GAP-G01** | Money Factory / Safety Gates | Production safety gates inspect immediate transaction amounts against AUTONOMOUS_SPEND_LIMIT_EUR (0.00). They lack visibility into deferred recurring obligations (e.g., $0 trial with $50/mo auto-renew or credit card pre-auth holds). | Multi-vector ZeroSpendBoundaryGovernor evaluating immediate spend, deferred liabilities, recurring cadence, and trial renewal clauses. Any potential liability must divert to Human Gate. | **P0** | REQUIRES_COMPOSITIONAL_ATTACK |
| **GAP-B01** | Supervisor / Lease Manager / Process Hygiene | Production process management issues SIGTERM/SIGKILL based solely on PID recorded in lease file. Under high process churn on Windows, PIDs recycle within seconds, risking killing innocent OS or IDE processes. | Tri-state process verification (MATCH, MISMATCH, UNKNOWN) comparing PID + CreationStartTimeMs + MachineId. Under UNKNOWN, SIGKILL is strictly forbidden. | **P0** | REQUIRES_COMPOSITIONAL_ATTACK |
| **GAP-C01** | Chief / Border Guard / Customs | Dispatches lack tamper-evident cryptographic sealing of the approved scope and acceptance criteria. A compromised or buggy planner can alter subtask definitions after human or policy approval. | Outbound task passport sealed with SHA-256 fingerprint of (goal_id, task_version, scope_hash, criteria_hash, approval_token). Inbound deliverable checked at Customs before merging. | **P1** | REQUIRES_BORDER_GUARD_REDTEAM |
| **GAP-W01** | Result Customs / Test Verifier | A worker reporting "ALL TESTS PASSED" may achieve this by deleting test files, skipping assertions, catching errors silently, or modifying thresholds. | Structural AST diff inspector verifying that test count, assertion count, and strict equality constraints did not decrease between pre-state and post-state. | **P1** | REQUIRES_AST_DETECTOR |
| **GAP-M01** | Storage / Journal Compaction / Migration | Loading legacy journals or event logs lacking task_version, process_start_time, or approval_token risks fabricating certainty or defaulting to unsafe states. | Deterministic migration adapter with explicit derivation rules: safely derivable fields populated; uncertain fields labeled UNKNOWN; hazardous operations placed on HOLD. | **P1** | REQUIRES_MIGRATION_ATTACK |
| **GAP-S01** | Autonomous Runtime / Long-Run Engine | Unattended long runs (>8h) risk journal unbounded growth, dangling leases from dead workers, and recurring task loops without progress. | Durable journal compaction with cryptographic anchor hashing, periodic monotonic lease sweep, anti-loop cycle detector, and autonomous self-generating backlog. | **P1** | REQUIRES_VIRTUAL_SOAK |

---

## 2. Compositional Risk Surface (The Target of Tonight)

Previous missions validated A01, L01, G01, and B01 in isolated single-component units.
Tonight's factory focuses on **Compound Failure Modes**:
- **Compound 1**: Uncertain Dispatch + Worker Fallback + Lease Expiry -> Duplication of external effects.
- **Compound 2**: Stale Approval Token + Schema Migration + Process Restart -> Privilege escalation or invalid write.
- **Compound 3**: PID Reuse + Supervisor Sweeper Cleanup + Delayed Result Arrival -> Killing innocent processes and accepting invalid deliverables.
- **Compound 4**: Parent/Child Resource Collisions + Worker Retries -> Corrupting parent directory artifacts during child failure.
- **Compound 5**: Human Gate + Auto-Renewing Zero-Euro Subscriptions + Generic User "Weiter" Input -> Financial commitment without explicit consent.
