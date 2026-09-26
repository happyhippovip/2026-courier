# TASK_18 — Worker Selection → Dispatch Trace

STATUS=DONE
FILE_LINE_EVIDENCE=server/app.py:260-350

## Dispatch
STATE_BEFORE=READY
STATE_AFTER=DISPATCHED
DISPATCH_ID=generated (uuid4 string)
ATTEMPT_ID=generated or incremented
PAYLOAD_RETURNED=full task dict with dispatch_id, attempt_id, target_capability, goal_id, task_id

## Physical Evidence
task-canary-B: DISPATCHED (confirmed in canary state)
dispatch_id visible in state JSON

PROVEN=Dispatch transition physically confirmed.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_19
