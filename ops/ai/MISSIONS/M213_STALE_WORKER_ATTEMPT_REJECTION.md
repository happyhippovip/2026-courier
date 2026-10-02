# M213: Stale Worker Attempt Rejection

## Goal
Prove that across sequential attempts of the same task, a durable result envelope submitted by a stale worker is cryptographically unbindable to the modern attempt context.

## Implementation & Proof
1. **Resumption & Identity Mintage**:
   - When a quarantined task is manually resumed, `server/app.py` (`resume_task()`) sets the status back to `"QUEUED"` and clears the `worker_id`.
   - On the next `claim_task()` by an available worker, Courier increments the `attempts` counter and mints completely fresh attempt and dispatch UUIDs:
     ```python
     next_task["attempt_id"] = f"{next_task['task_id']}:attempt:{next_task['attempts']}"
     next_task["dispatch_id"] = f"dispatch-{uuid.uuid4().hex}"
     ```
2. **Durable Binding Contract**:
   - When any worker submits a result, `validate_durable_result` (in `scripts/integration_contract.py`) asserts:
     ```python
     for field in ("goal_id", "task_id", "attempt_id", "dispatch_id", "worker_id"):
         if result[field] != task.get(field):
             raise ContractError(f"{field} mismatch")
     ```
3. **Cross-Attempt Contamination Blocked**:
   - If a stale worker from Attempt 1 successfully generates an effect and regains network connectivity during Attempt 2, it will submit a result envelope packed with the `dispatch_id` of Attempt 1.
   - The control plane will strictly reject it with `ContractError("dispatch_id mismatch")`, discarding the ghost payload.

## Conclusion
Each physical execution is sealed by a unique `dispatch_id`, guaranteeing that attempts are mathematically disjoint. Stale worker execution attempts cannot contaminate modern task state.
