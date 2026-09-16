# POST-FREEZE EXECUTION PLAN — COURIER INTEGRATION

- **Mission**: `WINDOWS_FINAL_INTEGRATION_REDTEAM_PACK_V1`
- **Execution Target**: Courier Production Mainline (Post-Freeze)
- **Standard**: Every stage is strictly bounded, deterministic, and independently verifiable with explicit automated tests, stop conditions, and rollback triggers.

---

## STAGE 1: CANDIDATE A01 (EXECUTION-UNCERTAINTY FENCE)

### 1. Preconditions
- Active Mac Courier lifecycle frozen and sealed.
- Working directory clean (`git status --porcelain` is empty).
- All pre-existing test suites passing.

### 2. Files
- `courier/core/dispatcher.js` (NEW or MODIFY)
- `courier/supervisor/types.js` (MODIFY)
- `tests/test_dispatcher_uncertainty_fence.js` (NEW)

### 3. Change
- Implement `DispatcherUncertaintyFence.assertDispatchPermitted(task, context)` at entry of `CourierDispatcher.dispatch()`.
- Add `HOLD_UNCERTAIN` and `DEPENDENCY_HELD_UNCERTAIN` to task status enums.
- Intercept all 14 caller triggers if task has `execution_uncertain === true` or `side_effect_uncertainty === true`.

### 4. Migration
- Execute atomic migration check on durable tasks: existing tasks with uncertain dispatches stamped `execution_uncertain: true`.

### 5. Targeted Test
- Run `node tests/test_dispatcher_uncertainty_fence.js`:
  - Verify all 14 indirect caller paths throw `SecurityBoundaryViolation` on uncertain task.
  - Verify certain tasks dispatch normally with zero latency degradation.

### 6. Independent Verification
- Run full regression smoke suite (`npm test`). Confirm exit code 0.

### 7. Rollback Point
- If regression observed: revert git commit `git revert HEAD --no-edit`. Uncertain tasks remain held by supervisor stall policy.

### 8. Stop Condition
- If any test fails or uncertain task escapes to worker: HALT IMMEDIATELY.

### 9. Next Stage
- Proceed to STAGE 2.

---

## STAGE 2: CANDIDATE L01 (HIERARCHICAL RESOURCE LOCKING)

### 1. Preconditions
- STAGE 1 verified and committed to mainline.
- Active leases file readable and valid JSON.

### 2. Files
- `courier/supervisor/resource_lock_manager.js` (NEW)
- `courier/supervisor/lease_manager.js` (MODIFY)
- `courier/supervisor/no_stacking.js` (MODIFY / DEPRECATE NAIVE DETECTOR)
- `tests/test_hierarchical_resource_locks.js` (NEW)

### 3. Change
- Replace naive `task_id === task_id` check with `ResourceLockManager`.
- Add `declared_resources` array to `createLease()`.
- Implement canonical path prefix comparison with trailing slash and platform case-folding.
- Support `tree:`, `file:`, `db:`, `port:`, `gitref:`.

### 4. Migration
- Run `migrateLegacyLease()` on `leases.json`: legacy un-scoped active leases stamped with `['tree:/']`.

### 5. Targeted Test
- Run `node tests/test_hierarchical_resource_locks.js`:
  - Verify parent/child directory overlap blocks concurrent execution.
  - Verify sibling directories execute in full parallel.
  - Verify Windows case-insensitive collision (`src/Core/` vs `src/core/`) blocks.

### 6. Independent Verification
- Run concurrency stress test with 10 concurrent synthetic workers.

### 7. Rollback Point
- Toggle `CONFIG.ENABLE_L01_HIERARCHICAL_LOCKS = false` in `supervisor/index.js`. Leases fall back to task-ID-only locking.

### 8. Stop Condition
- If deadlock or false-positive lock on unrelated tasks occurs: HALT.

### 9. Next Stage
- Proceed to STAGE 3.

---

## STAGE 3: CANDIDATE G01 (DEFERRED FINANCIAL LIABILITY GATE)

### 1. Preconditions
- STAGE 1 & STAGE 2 verified and committed.
- `AUTONOMOUS_SPEND_LIMIT_EUR = 0` confirmed active.

### 2. Files
- `courier/money_factory/safety_gates.js` (MODIFY)
- `courier/core/tool_runner.js` (MODIFY)
- `tests/test_deferred_liability_gate.js` (NEW)

### 3. Change
- Integrate `HardenedSafetyGate.evaluateIntent()` with deferred liability regex patterns (`auto-renew`, `free trial`, `billing agreement`).
- Hook tool runner capability barrier on financial endpoints (`stripe_charge`, `checkout_api`).
- Enforce single-use cryptographic approval tokens for human authorization.

### 4. Migration
- All existing tasks in `HUMAN_GATE` state require modern approval token upon human sign-off.
- Initialize `runtime/audit/consumed_approvals.jsonl`.

### 5. Targeted Test
- Run `node tests/test_deferred_liability_gate.js`:
  - Verify €0 free trials with auto-renew require `HUMAN_GATE`.
  - Verify analysis prompts ("simulate deployment") pass without gate.
  - Verify token replay and "weiter" text cannot authorize financial operations.

### 6. Independent Verification
- Test end-to-end checkout simulation tool; confirm execution is impossible without approval token.

### 7. Rollback Point
- Revert tool runner hook; `SafetyGateManager` falls back to static verb matching. `AUTONOMOUS_SPEND_LIMIT_EUR = 0` prevents actual spend.

### 8. Stop Condition
- Any bypass of financial gate: HALT IMMEDIATELY.

### 9. Next Stage
- Proceed to STAGE 4.

---

## STAGE 4: CANDIDATE B01 (MULTI-FACTOR PROCESS IDENTITY)

### 1. Preconditions
- STAGES 1-3 committed.
- Physical Mac host available for Darwin verification.

### 2. Files
- `courier/supervisor/process_identity.js` (NEW)
- `courier/supervisor/platform_darwin.c` (NEW - Darwin proc_pidinfo probe)
- `courier/supervisor/reconciliation.js` (MODIFY)
- `tests/test_process_identity_multifactor.js` (NEW)

### 3. Change
- On Mac host: compile and run `mac_proc_pidinfo_probe.c`. Confirm start-time retrieval under user permissions.
- In `lease_manager.js`: record `process_start_time_epoch_ms` and `task_token`.
- In `reconciliation.js`: match `(PID, StartTime, Token)`. If inspection fails, fail closed to `UNKNOWN` (never kill, never assume alive).

### 4. Migration
- Existing active leases lacking `start_time_epoch_ms` marked `identity_status: 'UNKNOWN'`.

### 5. Targeted Test
- Run `node tests/test_process_identity_multifactor.js`:
  - Simulate PID recycling; verify recycled process is recognized as mismatch and never killed.
  - Verify process with identical command but new start time is not conflated with old worker.

### 6. Independent Verification
- Run crash-restart chaos test with synthetic PID churning.

### 7. Rollback Point
- Set `CONFIG.ENABLE_B01_MULTI_FACTOR = false`. Process inspection reverts to passive PID tracking with kill disabled.

### 8. Stop Condition
- If unowned OS process receives kill signal: HALT IMMEDIATELY.

---

## SUMMARY OF HUMAN GATES FOR INTEGRATION
- Normal code editing, test running, and local migration do **NOT** require Human Gate.
- The following actions strictly **REQUIRE** Human Gate:
  1. Accessing production credentials or production cloud environments.
  2. Sudo or administrative privilege escalation on Mac or Windows hosts.
  3. Authorizing any real financial payment or live external trade (`SPEND_LIMIT_EUR = 0`).
  4. Pushing commits to public release repositories or publishing packages.
