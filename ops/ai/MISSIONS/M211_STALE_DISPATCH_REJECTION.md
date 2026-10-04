# M211: Stale Dispatch Rejection

## Goal
Prove that the Courier control plane safely quarantines a task dispatch if the worker goes offline without posting a durable result, thereby rejecting blind replays of ambiguous effects.

## Implementation & Proof
1. **Stale Worker Detection**:
   - `server/app.py` exposes `/tasks/reclaim_stale` which sweeps the worker registry for workers that have missed heartbeats (`now - w.get("last_seen", 0) > stale_threshold`).
2. **Ambiguous Effect Quarantine**:
   - For every goal in the system, it traverses the `workflow_plan`.
   - If a step is currently `"DISPATCHED"` and mapped to a worker determined to be stale, its status is mutated to `"HUMAN_REQUIRED"` with `recovery_reason = "STALE_WORKER_EFFECT_AMBIGUOUS"`.
   - The task and goal are marked `BLOCKED`.
3. **Safety Constraint**:
   - The system recognizes that the worker might have already created real-world side effects before crashing or losing network connectivity. Re-queueing the task automatically would risk an unsafe duplicate execution (`A_EXACTLY_ONCE` violation). By shifting it to a manual quarantine, a human operator can verify physical state before resuming the task.

## Conclusion
Courier rejects unsafe implicit retries of stale dispatches by aggressively quarantining them as ambiguous physical effects.
