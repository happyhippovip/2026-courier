# MAC-FINISH-07 — A-Execution Count Packet

## 1. Overview & Authority
- **Task ID**: MAC-FINISH-07
- **Area**: A_EXECUTION_COUNT_PACKET
- **Status**: COMPLETE

Asserts the mathematical singularity of Task A execution: Task A must execute exactly ONCE (`attempts == 1`).

---

## 2. Invariant Specifications
- `run.step_a.execution_count == 1`
- `attempts == 1` in coordinator central state
- `worker_invocations == 1` in worker execution telemetry
- Duplicate attempts (`attempts > 1`) constitute an immediate proof failure.

---

## 3. Coordinator Lock Enforcements
- Upon initial claim, coordinator sets `task["status"] = "IN_PROGRESS"`.
- Subsequent claim requests for `canary-task-a` return HTTP 409 Conflict.
- Upon completion, coordinator sets `task["status"] = "RECONCILED"`.
