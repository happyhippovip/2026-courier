# TASK_32: Duplicate / Retry: Conflicting Duplicate Result

STATUS=DONE
NEW_EVIDENCE=server/app.py:365: Submitting altered result payload (different hash/status) for already reconciled task returns HTTP 409 Conflict. Stored result is never overwritten.
PROVEN=Conflicting duplicate submissions fail closed.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_33
