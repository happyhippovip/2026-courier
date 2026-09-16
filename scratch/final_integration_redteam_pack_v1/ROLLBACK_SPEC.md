# ROLLBACK SPECIFICATION — COURIER POST-FREEZE INVARIANTS

- **Mission**: `WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1`
- **Scope**: Rollback procedures and safety guardrails for A01, L01, G01, and B01 in case of operational issues.

---

## 1. CORE ROLLBACK SAFETY INVARIANTS
1. **Never Restore Unsafe Semantics**:
   - A rollback of A01 code MUST NOT convert tasks marked `EXECUTION_UNCERTAIN` into `RETRYABLE` or `DISPATCHABLE`.
   - A rollback of B01 code MUST NOT convert `UNKNOWN` processes into `KILLABLE`.
   - A rollback of G01 code MUST NOT auto-approve pending financial commitments.
2. **Preserve Forensic Evidence**:
   - Audit logs, diagnostic bundles, and consumed token ledgers recorded under new code MUST NOT be deleted during rollback.
3. **Downward Schema Compatibility**:
   - Added schema fields (`declared_resources`, `process_start_time_epoch_ms`, `task_token`) must be ignored by older code without crashing.

---

## 2. COMPONENT-BY-COMPONENT ROLLBACK MATRIX

### A01: Execution-Uncertainty Fence Rollback
- **What Can Be Rolled Back**:
  - The central Dispatcher code assertion (`DispatcherUncertaintyFence.assertDispatchPermitted()`).
- **What CANNOT Be Erased**:
  - Any task that transitioned to `EXECUTION_UNCERTAIN` or `HOLD_UNCERTAIN` remains in that state. Older code inspecting `task.state === 'EXECUTION_UNCERTAIN'` continues to respect the supervisor blueprint invariant.
- **Rollback Guard**:
  - The feature flag `ENABLE_CENTRAL_DISPATCHER_FENCE` can be toggled to `false`. However, the fallback logic inside `RestartReconciler` and `StallPolicy` remains active.
- **Verification**: Verify that rolling back the fence does not cause an automatic burst of redispatches for existing uncertain tasks.

### L01: Hierarchical Resource Lock Rollback
- **What Can Be Rolled Back**:
  - The hierarchical path prefix and semantic conflict engine in `ResourceLockManager`.
- **What CANNOT Be Erased**:
  - Active write leases. Reverting code returns conflict detection to the naive `task_id === task_id` check.
- **Rollback Guard**:
  - All active leases with `declared_resources` continue to execute until normal completion. Unlocking logic safely strips the resource keys.
- **Verification**: Verify that tasks holding locks finish without throwing unhandled exceptions.

### G01: Deferred Liability Gate Rollback
- **What Can Be Rolled Back**:
  - The regex intent classifier and HTTP capability interceptor.
- **What CANNOT Be Erased**:
  - The append-only ledger `runtime/audit/consumed_approvals.jsonl`.
- **Rollback Guard**:
  - Reversion falls back to `SafetyGateManager.checkOperation()` and `price_eur > 0` validation. Because `AUTONOMOUS_SPEND_LIMIT_EUR = 0` remains hard-coded across all versions, autonomous spending remains impossible.
- **Verification**: Verify that pending `HUMAN_GATE` tasks remain blocked pending human sign-off.

### B01: Multi-Factor Process Identity Rollback
- **What Can Be Rolled Back**:
  - The Darwin `proc_pidinfo` / Win32 process inspection adapter and multi-factor matching logic.
- **What CANNOT Be Erased**:
  - Stored `process_start_time_epoch_ms` and `task_token` in `leases.json` (they remain passive metadata).
- **Rollback Guard**:
  - If B01 inspection causes high CPU or crashes, system falls back to passive PID checking. **CRITICAL GUARD**: Blind process termination is strictly disabled; any uncertain PID match defaults to `KEEP_RUNNING` or `WAIT`, never `TERMINATE`.
- **Verification**: Verify that innocent system processes are not sent `SIGKILL`.

---

## 3. ROLLBACK PROCEDURE WORKFLOW
1. **Stop Dispatcher Loop**: Pause intake of new tasks (`Courier.pause()`).
2. **Audit Active Leases**: Verify active leases are either in-flight or held.
3. **Apply Code Reversion**: Revert targeted git commit or disable corresponding feature flag:
   - `CONFIG.ENABLE_A01_FENCE = false`
   - `CONFIG.ENABLE_L01_HIERARCHICAL_LOCKS = false`
   - `CONFIG.ENABLE_G01_DEFERRED_GATE = false`
   - `CONFIG.ENABLE_B01_MULTI_FACTOR = false`
4. **Preserve Runtime Data**: Confirm `runtime/audit/` and `runtime/leases/` remain intact.
5. **Resume Dispatcher Loop**: Resume task processing in safe conservative mode.
