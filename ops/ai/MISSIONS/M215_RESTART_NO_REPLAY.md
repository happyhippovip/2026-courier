# M215: Restart No Replay

## Goal
Prove that if the physical worker daemon crashes or the host loses power mid-execution, the daemon safely releases the task on reboot rather than blindly replaying a potentially destructive payload.

## Implementation & Proof
1. **State Machine Durability**:
   - In `scripts/windows_worker/daemon.py`, the worker maintains a local, crash-safe state file (`current_task.json`) via atomic rename (`os.replace`).
2. **Execution Phase Tracking**:
   - The task progresses through strict phases: `"CLAIMED" -> "STARTED" -> "RESULT_READY"`.
3. **Crash Recovery Logic**:
   - When the daemon starts, it reads `current_task.json`. 
   - If it finds a task in the `"STARTED"` phase, it knows the task was interrupted mid-execution. Because the effect boundary was crossed, side effects may already exist.
   - The daemon immediately releases the task back to the server (`release_task = True`) and scrubs its local state.
   - The Courier control plane then marks the task `"HUMAN_REQUIRED"` because it was released without a result.

## Conclusion
Courier's physical worker design mathematically prevents blind replay of interrupted tasks, forcing safe manual recovery.
