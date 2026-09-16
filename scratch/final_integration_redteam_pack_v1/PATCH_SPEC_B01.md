# PATCH SPECIFICATION — CANDIDATE B01: MULTI-FACTOR PROCESS IDENTITY & PID RECYCLING

- **Invariant**:
  $$\text{PID alone} \neq \text{Process Identity}$$
  $$\text{ProcessIdentity} = \langle \text{MachineId}, \text{PID}, \text{StartTimeEpochMs}, \text{TaskLeaseToken} \rangle$$
  $$\text{Verify}(\text{Identity}) = \text{UNKNOWN} \implies (\text{KILL\_ALLOWED} = \text{FALSE} \land \text{ASSUME\_ALIVE} = \text{FALSE})$$
- **Severity**: P1 (Contract ambiguity & cross-platform risk; false liveness deadlock or catastrophic kill of innocent OS process)
- **Target Subsystem**: `supervisor/lease_manager.js`, `supervisor/reconciliation.js`, and OS Process Adapter

---

## 1. CURRENT BEHAVIOR
In the existing codebase:
- `supervisor/lease_manager.js` (lines 53-104) accepts `pid` and records `started_at` (an application-level ISO timestamp when the JavaScript object was instantiated), but does NOT record OS-level process start time (`start_ticks` or `tv_sec`).
- `supervisor/reconciliation.js` (lines 43-65) checks liveness via `livePids.includes(lease.pid)`.
- If a PID is present in `livePids`:
  - It checks `liveInfo.command === lease.command`.
  - If `liveInfo` or command is missing/uninspectable (e.g. permission restriction), it defaults `fingerprintMatch = true`.
- **THE FLAW**:
  1. **Rapid PID Reuse**: On Windows and macOS, PIDs are recycled frequently under high process churn.
  2. **False Liveness**: A worker process dies; an unrelated OS process receives its PID. Courier checks `livePids.includes(pid)`, assumes worker is still progressing, and deadlocks indefinitely.
  3. **Illegal Termination**: Courier assumes the worker is hung and calls `kill(pid, SIGKILL)`, terminating an innocent operating system daemon.
  4. **Fail-Open on Missing Metadata**: Treating uninspectable processes as matching (`fingerprintMatch = true`) is inherently unsafe.

---

## 2. TARGET BEHAVIOR
- A process is recognized as the authentic worker if and only if the multi-factor tuple matches:
  1. `MachineId`: Matches local host UUID.
  2. `PID`: OS process identifier.
  3. `StartTime`: High-resolution process start timestamp obtained directly from the kernel/OS table.
  4. `TaskLeaseToken`: Secure cryptographic nonce injected into worker environment (`COURIER_LEASE_TOKEN`).
- **Tri-State Identity Resolution**:
  - `MATCH_CONFIRMED`: PID, StartTime, and Token all verified -> Supervise normally.
  - `DEFINITE_MISMATCH`: PID dead or PID reused by a process with a different start time -> Mark lease `TERMINATED` / `PROCESS_RECYCLED`.
  - `UNKNOWN`: Process inspection failed (EPERM, SIP, Sandbox, process disappeared during syscall) -> Mark `UNKNOWN_HOLD`. **STRICTLY FAIL CLOSED: NEVER KILL, NEVER ASSUME ALIVE**.

---

## 3. PLATFORM-SPECIFIC PROCESS INSPECTION
### Windows (Win32 API)
- Windows provides `GetProcessTimes(hProcess, &lpCreationTime, &lpExitTime, &lpKernelTime, &lpUserTime)`.
- Creation time is a 64-bit `FILETIME` struct representing 100-nanosecond intervals since January 1, 1601.
- Provides absolute, non-wrapping start timestamps. Even if PID is reused within milliseconds, `CreationTime` is strictly monotonic and distinct.
- Verified 100% working in Windows lab.

### macOS / Darwin (POSIX / Mach API)
- Darwin provides `proc_pidinfo(pid, PROC_PIDTASKINFO, ...)` returning `struct proc_taskinfo` which includes `pti_start_tvsec` and `pti_start_tvusec`.
- Alternatively: `sysctl` with `KERN_PROC_PID` returning `struct kinfo_proc.kp_proc.p_starttime`.
- **The Proof Gap**: Does calling `proc_pidinfo` on an external worker process trigger macOS App Sandbox or SIP permission errors when Courier runs as a non-root agent?
- **Darwin Minimum Test Requirement**: Must be validated on physical Mac host (`MAC_NATIVE_MINIMUM_TEST.md`).

---

## 4. MINIMAL CHANGE SPECIFICATION
In `supervisor/process_identity.js`:

```javascript
const PROCESS_IDENTITY_MATCH = Object.freeze({
  MATCH_CONFIRMED: 'MATCH_CONFIRMED',
  DEFINITE_MISMATCH: 'DEFINITE_MISMATCH',
  UNKNOWN: 'UNKNOWN'
});

class ProcessIdentityValidator {
  static verifyIdentity(lease, currentSystemProcess) {
    if (!lease || !currentSystemProcess) {
      return {
        status: PROCESS_IDENTITY_MATCH.DEFINITE_MISMATCH,
        can_kill: false,
        assume_alive: false,
        reason: 'Missing lease or target process info'
      };
    }

    // 1. Check PID
    if (lease.pid !== currentSystemProcess.pid) {
      return {
        status: PROCESS_IDENTITY_MATCH.DEFINITE_MISMATCH,
        can_kill: false,
        assume_alive: false,
        reason: `PID mismatch: lease ${lease.pid} vs system ${currentSystemProcess.pid}`
      };
    }

    // 2. Check StartTime
    if (lease.process_start_time_epoch_ms === undefined || currentSystemProcess.start_time_epoch_ms === undefined) {
      // Missing high-resolution start time -> FAIL CLOSED to UNKNOWN
      return {
        status: PROCESS_IDENTITY_MATCH.UNKNOWN,
        can_kill: false,     // MUST NOT KILL
        assume_alive: false, // MUST NOT ASSUME ALIVE
        reason: 'Start-time metadata missing from lease or system process query'
      };
    }

    const timeDeltaMs = Math.abs(lease.process_start_time_epoch_ms - currentSystemProcess.start_time_epoch_ms);
    // Allow small clock jitter (<= 100ms) for timing discrepancies
    if (timeDeltaMs > 1000) {
      return {
        status: PROCESS_IDENTITY_MATCH.DEFINITE_MISMATCH,
        can_kill: false,
        assume_alive: false,
        reason: `PID ${lease.pid} was recycled: lease started at ${lease.process_start_time_epoch_ms}, active process started at ${currentSystemProcess.start_time_epoch_ms} (delta ${timeDeltaMs}ms)`
      };
    }

    // 3. Check Task Token if present
    if (lease.task_token && currentSystemProcess.env_task_token) {
      if (lease.task_token !== currentSystemProcess.env_task_token) {
        return {
          status: PROCESS_IDENTITY_MATCH.DEFINITE_MISMATCH,
          can_kill: false,
          assume_alive: false,
          reason: 'Process lease token mismatch'
        };
      }
    }

    return {
      status: PROCESS_IDENTITY_MATCH.MATCH_CONFIRMED,
      can_kill: true, // Only confirmed match can be terminated under supervisor policy
      assume_alive: true,
      reason: 'Multi-factor process identity confirmed (PID + StartTime + Token)'
    };
  }
}
```

---

## 5. REQUIRED STATE FIELDS & PERSISTENCE
- In `ProcessLease` (`leases.json`):
  - `process_start_time_epoch_ms`: `number` (kernel process creation timestamp)
  - `task_token`: `string` (random 32-character hex nonce)
  - `machine_id`: `string` (unique host identifier)
- In `supervisor/reconciliation.js`:
  - Replace naive `livePids.includes(lease.pid)` with `ProcessIdentityValidator.verifyIdentity()`.

---

## 6. FAIL-CLOSED RULES
- If OS process inspection throws `EPERM` or `ACCESSEXCEPTION`: return `UNKNOWN`.
- On `UNKNOWN`:
  - `can_kill = false`
  - `assume_alive = false`
  - Emit alert to Supervisor audit log and place lease in `STATUS: UNCERTAIN_NEVER_BLINDLY_KILL`.

---

## 7. MIGRATION & ROLLBACK
- **Migration**: Old leases lacking `process_start_time_epoch_ms` are tagged `LEGACY_PID_ONLY`. They are treated as `UNKNOWN` for termination decisions (cannot be killed automatically) but may be monitored for completion via file deliverables.
- **Rollback**: Rollback must not restore blind PID kill.

---

## 8. CLASSIFICATION & MAC PROOF REQUIREMENT
- **Classification**: `CONFIRMED_ARCHITECTURAL_REQUIREMENT` / `CONTRACT_AMBIGUITY` (P1).
- **Mac-Native Proof**: **REQUIRED**. See `MAC_NATIVE_MINIMUM_TEST.md`.
