# RUNTIME DESIGN: WINDOWS COURIER MINIMAL PRODUCTION RUNTIME V1

## 1. Architectural Philosophy & Constraints
- **95% Wiring, 5% Outer-Loop Control**: Zero new authorities. Reuse all existing canonical modules in `governance/` and `supervisor/`.
- **Single Canonical Entrypoint**: `bin/courier_runtime.js` executable via Node.js CLI.
- **Autonomous Continuum**: Accepts ONE high-level goal, autonomously derives work units, routes, acquires locks, mints passports, executes via BorderGuard, checks customs, verifies evidence, and queries CompletionGovernor.
- **Strict Invariants**:
  - `AUTONOMOUS_SPEND_LIMIT_EUR = 0`
  - Real trades = 0, Real funds = 0, Wallets = 0
  - Mac host access = DENIED
  - universuX = DENIED
  - RELEASE_CANDIDATE_V1 = IMMUTABLE (Untouched)

---

## 2. Component Pipeline & Information Flow

```text
[ CLI INVOCATION ]
   node bin/courier_runtime.js --goal "..." --allowed-root <dir> --state-dir <dir>
           |
           v
[ 1. BOOT & RECONCILIATION ]
   - Initialize SupervisorPlane, AuditLedger, LeaseManager, LockManager
   - Load durable mission state from disk if resuming
   - Invoke RestartReconciler to fence unconfirmed mid-flight leases
           |
           v
[ 2. GOAL INTAKE & CLASSIFICATION ]
   - CrossDeviceIntakeEngine.classifyAndRoute(goal)
   - Enforce ActionDomain == LOCAL_MACHINE
   - Fail-closed on HumanGate or remote delegation
           |
           v
[ 3. AUTONOMOUS TASK DERIVATION ]
   - Scan allowed-root fixture workspace for operational inconsistencies
   - Derive structured tasks with task_id, version, scope, acceptance, worker
           |
           v
+--------> [ 4. AUTONOMOUS TASK LIFECYCLE LOOP ]
|          |
|          v
|     [ 4a. WORKER NEGOTIATION & NO-STACKING ]
|          - Check ResourceLockManager. If target locked -> defer to FollowUpInbox
|          v
|     [ 4b. TASK PASSPORT STAMPING ]
|          - TaskPassport.createPassport(task, allowed_root, capability)
|          v
|     [ 4c. BORDER GUARD PRE-DISPATCH CHECK ]
|          - DecisionEngine.evaluatePreDispatchAdmission(task, passport, lockManager)
|          - Reject if stale passport, capability breach, or lock collision
|          v
|     [ 4d. PROCESS LEASE & LOCK ACQUISITION ]
|          - ResourceLockManager.acquire(scopePath, taskId)
|          - ProcessLeaseManager.createLease(composite identity: PID + start_time + token)
|          v
|     [ 4e. BOUNDED LOCAL WORKER EXECUTION ]
|          - LocalWorkerAdapter executes work strictly inside allowed-root
|          - Emits output artifacts and exit code
|          v
|     [ 4f. RESULT CUSTOMS INTAKE ]
|          - ResultCustoms.evaluateResultEnvelope(task, passport, exit_code, artifacts)
|          - Reject worker prose; require exit code 0 and verifiable files
|          v
|     [ 4g. INDEPENDENT EVIDENCE VERIFICATION ]
|          - ResultCustoms.validateArtifactIntegrity(artifacts, checksum_map)
|          - Cryptographic SHA-256 disk verification
|          v
|     [ 4h. COMPLETION GOVERNOR EVALUATION ]
|          - CompletionGovernor.evaluateWorkerReport(report) -> Worker DONE rejected
|          - Release resource lock, complete process lease
|          - CompletionGovernor.evaluateMissionStatus(mission)
|          - If terminal (SATISFIED/BLOCKED) -> BREAK LOOP
|          v
|     [ 4i. AUTONOMOUS NEXT-BEST-WORK SELECTION ]
|          - Check FollowUpInbox for unblocked deferred work
|          - Rank frontier tasks by impact, risk, and readiness
|          - Checkpoint durable mission state to disk
|          +--- Loop back to next task
           |
           v
[ 5. MISSION TERMINATION & SUMMARY ]
   - Write final durable state
   - Log terminal event to AuditLedger
   - Exit cleanly with code 0
```

---

## 3. CLI Interface
```bash
node bin/courier_runtime.js \
  --goal "<Goal String>" \
  --allowed-root "<Absolute Path to Workspace>" \
  --state-dir "<Path to State Directory>" \
  --offline \
  --spend-limit-eur 0
```

---

## 4. File Footprint
- **New Production File**: Exactly ONE file: `courier/bin/courier_runtime.js`.
- **Existing Production Files Modified**: ZERO.
