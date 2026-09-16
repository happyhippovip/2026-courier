# PATCH SPECIFICATION — CANDIDATE A01: EXECUTION-UNCERTAINTY FENCE

- **Invariant**:
  $$\text{task.state} \in \{\text{EXECUTION\_UNCERTAIN}, \text{POSSIBLE\_SIDE\_EFFECT}\} \implies \text{AUTO\_REDISPATCH} = \text{BLOCKED}$$
- **Severity**: P0 (Catastrophic duplicate execution / financial liability / worktree clobbering)
- **Target Subsystem**: Courier Central Dispatch & Task State Machine

---

## 1. CURRENT BEHAVIOR
In the existing codebase:
- `SUPERVISOR_PLANE_ARCHITECTURE.md` (lines 59-64) documents that `EXECUTION_UNCERTAIN` tasks must never be retried or duplicate-dispatched without human verification.
- `supervisor/reconciliation.js` (lines 104-132) correctly marks pending tasks without proof of effect or non-effect as `EXECUTION_UNCERTAIN` and emits audit events.
- `supervisor/stall_policy.js` (lines 48-56) returns decision `BLOCK_EXECUTION_UNCERTAIN`.
- **THE FLAW**: There is NO centralized gating fence in Courier's central dispatch pathway. Individual caller subsystems (Supervisor stall detection, Task Hygiene lease reclamation, Resource Governor rerouting, and Router timeout fallback handlers) independently decide to reissue tasks when an active lease dies or times out. Because they check only `!task.isCompleted() && lease.isFree()`, an uncertain task is redispatched to a second worker, executing duplicate mutative actions.

---

## 2. TARGET BEHAVIOR
- Any call to dispatch, retry, reroute, fallback, or restart a task MUST pass through an unconditional choke point in `CourierDispatcher.dispatch()`.
- If `task.state === 'EXECUTION_UNCERTAIN'` or `task.side_effect_uncertainty === true` or `task.has_unsettled_side_effects === true`:
  - Central dispatcher throws a fatal `SecurityBoundaryViolation: [DISPATCH_FENCE_UNCERTAIN_BLOCKED]`.
  - Task state transitions to `HOLD_UNCERTAIN`.
  - No worker is allocated; no subprocess is spawned; no network call is emitted.
  - Dependent tasks (tasks declaring a dependency on this task) are also transitioned to `DEPENDENCY_HELD_UNCERTAIN`.
  - Only an explicit, cryptographically authenticated Human Settlement Attestation can clear the fence.

---

## 3. CALL-PATH INVENTORY (ALL 14 WINDOWS-VISIBLE DISPATCH PATHS)
Every entry point in the architecture that can trigger task execution:
1. `Router.routeTask()`: Initial direct dispatch from task backlog.
2. `Router.handleWorkerTimeout()`: Fallback dispatch to secondary worker upon lease timeout.
3. `Router.handleWorkerError()`: Automatic retry on transient worker failure.
4. `Supervisor.decisionEngine.evaluate()`: `TERMINATE_HUNG` followed by replan/requeue.
5. `Supervisor.stallPolicy`: Process stalled threshold triggering worker replacement.
6. `MachineResourceGovernor.evaluateTaskAdmission()`: `RECOMMEND_REROUTE` dispatching task to another machine.
7. `RestartReconciler.reconcile()`: Post-crash recovery loop processing uncompleted tasks.
8. `TaskHygiene.runTaskHygiene()`: Cleaning dead workers and attempting to re-enqueue unfinished work.
9. `ResultCustoms.validateDeliverables()`: Rejection of incomplete artifact triggering retry.
10. `ChiefEscalationEnvelope.re-dispatch()`: Chief automated review returning task to queue.
11. `Planner.replan()`: Dynamic decomposition reissuing modified task slice.
12. `ManualWeiterHandler.resume()`: Autonomous resumption from checkpoint re-evaluating queue.
13. `WorkerReconnectHandler.onReconnect()`: Worker re-announcing and taking next queue item.
14. `TransitiveDependencyTrigger.onParentComplete()`: Automatic dispatch of downstream child tasks.

**Narrowest Enforcement Point**: `CourierDispatcher.dispatch()`. All 14 paths converge on this single method to obtain a worker lease and start execution.

---

## 4. CHALLENGING THE CHOKE POINT ASSUMPTION (BYPASS ANALYSIS)
Can any worker/effect begin without passing `CourierDispatcher.dispatch()`?
- **Attack Vector 1**: Worker process reconnects after network partition and executes already-dispatched instructions from local buffer.
  - *Mitigation*: The worker must re-validate its lease with `CourierDispatcher.validateLease(leaseId)` before executing each step. If lease is marked `EXECUTION_UNCERTAIN`, worker receives `ABORT_IMMEDIATELY`.
- **Attack Vector 2**: Direct subprocess spawn inside a tool handler (bypassing dispatcher).
  - *Mitigation*: Tool execution layer enforces that all tool runners receive a signed execution context tied to the active lease.
- **Attack Vector 3**: Transitive dependencies: Task $T_1$ is uncertain, but downstream Task $T_2$ runs because its trigger only checked $T_1$'s exit code or file existence.
  - *Mitigation*: Transitive dependency resolution must explicitly inspect parent task `state !== EXECUTION_UNCERTAIN`.

---

## 5. MINIMAL CHANGE SPECIFICATION
In `courier/core/dispatcher.js` (or `supervisor/dispatcher_fence.js` integration hook):
```javascript
class DispatcherUncertaintyFence {
  static assertDispatchPermitted(task, context = {}) {
    if (!task) {
      throw new SecurityBoundaryViolation('[DISPATCH_FENCE_ERROR] Task is required');
    }

    // 1. Direct uncertainty check
    if (task.state === 'EXECUTION_UNCERTAIN' || task.execution_uncertain === true) {
      throw new SecurityBoundaryViolation(
        `[DISPATCH_FENCE_UNCERTAIN_BLOCKED] Task ${task.id} is marked EXECUTION_UNCERTAIN. ` +
        `Automatic redispatch/fallback/retry is strictly forbidden without human proof.`
      );
    }

    // 2. Unsettled side-effect check
    if (task.side_effect_uncertainty === true || task.side_effect_potential === 'POSSIBLE_UNSETTLED') {
      throw new SecurityBoundaryViolation(
        `[DISPATCH_FENCE_SIDE_EFFECT_BLOCKED] Task ${task.id} has unsettled side-effects. ` +
        `Redispatch blocked until settlement verification is completed.`
      );
    }

    // 3. Transitive dependency inheritance check
    if (Array.isArray(task.dependencies) && task.dependencies.length > 0) {
      const taskStore = context.taskStore;
      if (taskStore) {
        for (const depId of task.dependencies) {
          const dep = taskStore.getTask(depId);
          if (dep && (dep.state === 'EXECUTION_UNCERTAIN' || dep.execution_uncertain === true)) {
            throw new SecurityBoundaryViolation(
              `[DISPATCH_FENCE_TRANSITIVE_UNCERTAIN_BLOCKED] Task ${task.id} depends on task ${depId} ` +
              `which is in EXECUTION_UNCERTAIN state.`
            );
          }
        }
      }
    }

    return true;
  }
}
```

---

## 6. REQUIRED METADATA & PERSISTENCE
- **State Fields**:
  - `task.state`: `EXECUTION_UNCERTAIN` | `HOLD_UNCERTAIN` | `DEPENDENCY_HELD_UNCERTAIN`
  - `task.execution_uncertain`: `boolean` (default `false`)
  - `task.side_effect_uncertainty`: `boolean` (default `false`)
  - `task.side_effect_potential`: `'NONE'` | `'POSSIBLE_UNSETTLED'` | `'SETTLED'`
  - `task.uncertainty_reason`: `string`
  - `task.uncertainty_timestamp`: `ISO8601`
- **Persistence Boundary**:
  - Must be recorded in durable task store and lease file (`runtime/leases/leases.json`).
  - Write MUST sync (`fs.renameSync` or atomic fsync) before lease or task is released.

---

## 7. FAIL-CLOSED RULES
- If task metadata is missing or corrupted: default to `EXECUTION_UNCERTAIN`.
- If external verification query times out: remain in `EXECUTION_UNCERTAIN`.
- If task store cannot be read: block all dispatch (`FAIL_CLOSED_SYSTEM_HALT`).

---

## 8. MIGRATION & ROLLBACK
- **Migration**: Existing active tasks without `execution_uncertain` field default to `false` unless status is currently unproven post-restart, in which case `RestartReconciler` stamps `true`.
- **Rollback**: Disabling the fence must NOT reset existing `EXECUTION_UNCERTAIN` tasks to `PENDING` or `RETRYABLE`. Historical uncertainty markings are immutable.

---

## 9. CLASSIFICATION & REMAINING GAPS
- **Classification**: `LIKELY_PRODUCTION_DEFECT` / `CONFIRMED_ARCHITECTURAL_REQUIREMENT` (P0).
- **Mac-Native Proof**: None required (deterministic JavaScript state-machine logic).
