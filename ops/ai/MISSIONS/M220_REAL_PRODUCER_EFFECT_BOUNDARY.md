# M220: Real Producer Effect Boundary

## Goal
Prove that Courier perfectly delineates the threshold where a physical execution produces real-world side effects.

## Implementation & Proof
1. **State Machine Logging (`daemon.py`)**:
   - When a worker claims a task, it writes `"worker_phase": "CLAIMED"` to its local `current_task.json`. At this stage, NO instruction has been executed. The task can be safely abandoned or reassigned.
2. **The Execution Boundary**:
   - Just milliseconds before invoking the physical command (`subprocess.Popen`), the daemon rewrites the local state to `"worker_phase": "STARTED"`.
3. **Effect Assumption**:
   - If the host crashes immediately after writing `"STARTED"`, the worker on reboot will assume that real-world effects (like file creation, network transmission, or state mutation) have already occurred.
   - It will unconditionally release the task to the control plane rather than attempting an unsafe retry.

## Conclusion
Courier strictly guarantees that the boundary between a harmless claim and a physical side effect is bounded by a synchronous local disk write.
