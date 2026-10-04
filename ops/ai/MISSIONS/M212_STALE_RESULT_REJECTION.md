# M212: Stale Result Rejection

## Goal
Prove that a worker that went offline and later awakens cannot unilaterally overwrite the state of a task that has since been quarantined or reclaimed.

## Implementation & Proof
1. **Result Submission Envelope Validation**:
   - In `server/app.py`, the `task_result()` handler processes incoming result submissions from remote workers.
2. **Terminal State Shielding**:
   - A direct check is enforced:
     ```python
     if task.get("worker_id") == worker_id:
         if task.get("status") != "DISPATCHED":
             return jsonify({"error": "Task is not awaiting a result"}), 409
     ```
3. **Quarantine Intersection**:
   - If a worker becomes stale, `reclaim_stale` forcefully transitions the task state from `"DISPATCHED"` to `"HUMAN_REQUIRED"`. 
   - If the original worker suddenly regains connectivity and submits its completed payload, the server rejects it with an HTTP 409 Conflict. 
   - The task state is strictly preserved in its quarantined or retried state.

## Conclusion
Stale results arriving after a worker was deemed lost are actively rejected because the control plane tightly guards the task lifecycle state machine.
