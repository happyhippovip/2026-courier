# M214: Verify Reconcile Next Ready

## Goal
Prove that Courier sequentially unblocks downstream tasks within a workflow plan only after the independent verifier successfully reconciles the prior task.

## Implementation & Proof
1. **Goal Advancement Engine**:
   - In `server/app.py` (`verify_task_result`), once the verifier submits a valid independent verification for a `"RESULT_RECEIVED"` task, the task is elevated to `"RECONCILED"`.
2. **Next-Step Unblocking**:
   - The reconciliation handler linearly iterates through the `workflow_plan` of the bound goal.
   - It marks the current step as `"SUCCESS"`.
   - It looks ahead precisely one index (`current_step_index + 1 < len(plan)`).
   - If the subsequent task is in a `"BLOCKED"` state, it mutates its status to `"QUEUED"`. 
3. **Safety Guarantee**:
   - A task cannot enter the global `"QUEUED"` pool until its strictly preceding dependent task is both fully executed by a worker AND cryptographically verified by the independent verifier. 

## Conclusion
Courier enforces strict linear sequence execution in a workflow plan by utilizing the verifier's reconciliation signature as the unblocking trigger.
