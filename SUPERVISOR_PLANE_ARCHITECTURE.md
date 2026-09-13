# Courier Supervisor Plane P0 — Architecture & Runtime Blueprint

## 1. What Problem This Solves
Long-running autonomous agent tasks, test suites, and worker processes frequently encounter quiet periods, slow compilation steps, network waits, or deadlocks. Without supervisor discipline, systems fall into two failure modes:
1. **Premature Kill**: A naive timeout aborts a progressing 20-minute compile or test suite simply because time elapsed.
2. **Silent Zombie Accumulation**: Stalled or deadlocked processes, obsolete `tail -f` / `lldb` helpers, and duplicate test suites stack up, exhausting system memory, file handles, and causing thermal runaway (as seen on the Mac).

The **Supervisor Plane** provides deterministic, evidence-based runtime supervision. It diagnoses stalls, captures forensic bundles without human intervention, cleans obsolete helper processes, prevents duplicate work, protects against thermal exhaustion, and preserves uncertain execution state across restarts.

---

## 2. Canonical Pipeline

```text
TASK STAMP
→ WORKER LEASE
→ PROCESS LEASE
→ HEARTBEAT
→ PROGRESS EVIDENCE
→ RESOURCE GOVERNOR
→ STALL DETECTION
→ DIAGNOSTIC
→ SUPERVISOR DECISION
→ TASK HYGIENE
→ RESULT CUSTOMS
→ CLOSE
```

1. **TASK STAMP**: Canonical task identity stamped by Courier.
2. **WORKER LEASE**: Machine & worker allocation.
3. **PROCESS LEASE**: Durable attribution of OS process (PID, command fingerprint, cleanup policy).
4. **HEARTBEAT**: Periodic liveness ping.
5. **PROGRESS EVIDENCE**: Verifiable external artifacts (log growth, test completion, file writes).
6. **RESOURCE GOVERNOR**: Per-machine thermal and heavy-concurrency admission control.
7. **STALL DETECTION**: 5-min soft check (`CHECK_PROGRESS`), 15-min threshold (`CAPTURE_DIAGNOSTIC`).
8. **DIAGNOSTIC**: Isolated bundle creation (`runtime/diagnostics/<id>/`).
9. **SUPERVISOR DECISION**: Deterministic classification (`KEEP_RUNNING`, `WAIT`, `CAPTURE_DIAGNOSTIC`, `TERMINATE_ORPHAN`, etc.).
10. **TASK HYGIENE**: Automatic cleanup of obsolete helper processes at task completion.
11. **RESULT CUSTOMS**: Formal validation of deliverable artifacts before closing the lease.
12. **CLOSE**: Final append-only audit event and lease archiving.

---

## 3. Core Invariants & Epistemology

### Why Elapsed Time Alone Cannot Define "Hung"
A quiet process is not necessarily hung. A heavy compile, large dataset export, or neural model inference may emit zero stdout lines for several minutes while actively utilizing CPU or waiting on an OS lock. Time alone **must never cause termination**. A process can only be classified as `HUNG` and terminated if:
1. Diagnostic threshold (900s) has been exceeded;
2. Diagnostic bundle has been captured;
3. Zero CPU utilization is verified;
4. Unresponsive process ping is confirmed.

### Why Screenshots Are Secondary Fallback Only
Screenshots are expensive, opaque to machine diffs, and pose severe privacy and security risks (accidental leakage of API keys, OTP codes, wallet secrets, or private tabs). The Supervisor Plane prioritizes deterministic text evidence (process exit codes, log deltas, git diffs, resource metrics). A screenshot spec is triggered only if text evidence is completely unavailable, and the target window is strictly scanned by the **Privacy Guard** (`SCREENSHOT_BLOCKED_PRIVACY`).

### How PROCESS_LEASE Works
Every long-running command acquired by a worker creates a durable lease record in `runtime/leases/leases.json`. Leases track parent-child relationships, command fingerprints, started timestamps, and explicit cleanup policies (`TERMINATE_ON_TASK_END` vs. `PRESERVE_BACKGROUND`). Leases persist across restarts.

### How Restart Recovery & EXECUTION_UNCERTAIN Work
On system reboot or agent restart, the `RestartReconciler` compares active system PIDs against durable leases:
- Known live progressing processes resume supervision.
- Unowned live processes are marked `UNATTRIBUTED_NEVER_BLINDLY_KILL` to prevent killing critical system tools.
- **The Uncertainty Invariant**: If a task was dispatched before the restart but lacks durable proof of either completion or non-dispatch, it is marked `EXECUTION_UNCERTAIN`. Under this state, **NO redispatch, NO retry, and NO duplicate execution** is permitted until manual human verification or external settlement proof is provided.

### Per-Machine Resource Isolation (Why a Hot Mac Does Not Throttle Healthy Windows)
Resource governance is strictly **per-machine**, never global:
- The Mac environment is constrained by hardware thermals and uses `MAX_CONCURRENT_HEAVY_LOCAL_TASKS = 1`. Under thermal pressure, the Mac halts **new** heavy tasks and emits `RECOMMEND_REROUTE`.
- The Windows environment is healthy and independently configured (`MAX_CONCURRENT_HEAVY_LOCAL_TASKS = 4`). It continues accepting and executing heavy tasks without being throttled by Mac's thermal state.

---

## 4. Integration Boundary (Courier & Chief)

The Supervisor Plane is an auxiliary domain layer, **NOT a second orchestrator**. Courier remains the sole canonical orchestrator.

### Future Integration Points:
- **Courier Task Dispatch**: Acquires lease via `ProcessLeaseManager.createLease()` and checks `MachineResourceGovernor.evaluateTaskAdmission()`.
- **Worker Execution**: Emits periodic progress via `ProgressTracker.recordProgress()`.
- **Task Completion**: Calls `TaskHygiene.runTaskHygiene()` to terminate obsolete watchers (`tail`, `lldb`) while preserving background services (`PRESERVE_BACKGROUND`).
- **Escalation**: When an autonomous decision cannot be safely reached, Courier generates a `ChiefEscalationEnvelope` (`SUPERVISOR_REVIEW_REQUEST`) containing diagnostic bundle pointers for review.

---

## 5. What Remains Intentionally Unbuilt
- **Invasive OS Window Automation**: GUI click/capture drivers intentionally omitted.
- **External Network Dispatchers**: Cloud telemetry and external HTTP webhooks intentionally omitted.
- **Automatic System Power / Sudo Tweaks**: Sudo, admin elevation, or altering OS power plans are strictly forbidden.
- **Second Task Queue**: Courier retains exclusive ownership of mission scheduling.
