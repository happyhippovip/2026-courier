# TASK_15 — Verification → Reconcile Trace

STATUS=DONE
NEW_EVIDENCE=physically proven + candidate-b-1

FILE_LINE_EVIDENCE=server/app.py:466-500 (verify_task_result)

## Reconcile Logic
1. Verify result_id matches task["result"]["result_id"]
2. Verify artifacts match task["result"]["artifacts"]
3. Set task["status"] = "RECONCILED"
4. Persist state file atomically
5. Return {"status": "RECONCILED"}

## Idempotency (candidate-b-1)
FILE_LINE_EVIDENCE=server/app.py:479
If task already RECONCILED with same result_id → ACK_DUPLICATE (HTTP 200)

## Known Bug (production 332a42f9)
FILE_LINE_EVIDENCE=server/app.py:490 (plan desync bug)
goal["workflow_plan"] step status NOT updated on reconcile.
Effect: step UI shows stale DISPATCHED even after RECONCILED.
Workaround: query task directly, not via workflow plan.
Status: BUG, but does NOT block A→VERIFY→B physical run.

PROVEN=Reconcile physically proven. task-canary-A shows RECONCILED in canary state.
UNKNOWN=Whether plan desync is fixed in candidate-b-1 (not audited; not on critical path).
BLOCKER=None
NEXT=TASK_16
