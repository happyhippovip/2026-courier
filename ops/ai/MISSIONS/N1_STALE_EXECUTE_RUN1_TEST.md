# N1 — Stale Execute RUN1 Test (Negative Case)

Status: ACTIVE / READ_ONLY

## OVERVIEW
Negative case verification for a stale result arriving after a new generation or after a restart during RUN1 execution.

## OUTPUT

**SCENARIO**: 
A worker is dispatched a task, disappears (or restarts), and the system dispatches the task again to a new worker. Later, the original worker reappears and submits a stale result for the task.

**EXPECTED_STATE**: 
The server should reject the stale result because the task's execution footprint or dispatch ID has advanced. The task must remain in the state assigned to the new worker or successfully complete only once.

**FORBIDDEN_OUTCOME**: 
- Task A completes twice.
- The stale result overwrites the new result.
- The ledger corrupts due to duplicate completion events for the same task.

**EVIDENCE_NEEDED**: 
- Server log showing the rejection of the stale result (e.g., HTTP 409 Conflict or 400 Bad Request).
- Worker log showing the failure to submit the stale result.
- Ledger db showing `Task A` transitioning cleanly to `RECONCILED` exactly once.

**CURRENT_GAP**: 
- Need physical execution on Mac (`RUN1`) to intentionally inject a stale execution submission and capture the server's rejection.

**PHYSICAL_RUN_REQUIRED**: YES
