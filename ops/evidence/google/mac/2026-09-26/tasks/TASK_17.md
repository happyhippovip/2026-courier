# TASK_17: Trace: READY -> Worker Selection

STATUS=DONE
NEW_EVIDENCE=Trace server/app.py:300-340. Worker calls POST /tasks/claim. Server matches next step's target_agent/target_capability against worker capabilities.
PROVEN=Worker capability matching gates claim. Unmatched or busy worker receives null task.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_18
