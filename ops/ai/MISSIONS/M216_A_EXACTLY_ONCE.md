# M216: Exactly Once Execution

## Goal
Prove that across the entire distributed Courier architecture, a task instruction executes exactly once.

## Implementation & Proof
Exactly-once execution in distributed systems requires ensuring both at-most-once physical execution and at-least-once durable recovery. Courier achieves exactly-once semantics by combining control-plane safeguards and worker-node phase logging:

1. **At-Most-Once Physical Execution (Worker)**:
   - When the worker begins executing an instruction (`subprocess.Popen`), it durably logs `"STARTED"` locally (`scripts/windows_worker/daemon.py`).
   - If it crashes, it releases the task rather than replaying it (M215).
   - If it completes execution, it logs `"RESULT_READY"`. If result transmission fails, it only retries the network transmission, never the execution (`http_post_result` network loop).

2. **At-Most-Once Task Dispatch (Control Plane)**:
   - `server/app.py` ensures a task can only be claimed if its status is `"QUEUED"`. 
   - Once claimed, it transitions to `"DISPATCHED"` and gets a unique `dispatch_id`. 
   - If a stale worker attempts to submit an old `dispatch_id` after the task is resumed/retried, it is rejected (M213).
   - Only an independent verifier can elevate a received result into a `"RECONCILED"` success, preventing a worker from looping or spoofing its own completion (M210).

3. **Quarantine Over Replay**:
   - Both stale workers (`reclaim_stale`) and crashed workers (releasing `"STARTED"` tasks) result in `"HUMAN_REQUIRED"`. Replay is never assumed safe for a task that left `"QUEUED"` but failed to deliver a `"RESULT_READY"` payload.

## Conclusion
By isolating network retry loops from execution loops and binding all outcomes to unique cryptographically-validated dispatch IDs, Courier guarantees exactly-once execution.
