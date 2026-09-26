# TASK_37: Duplicate / Retry: STARTED Ambiguity After Restart

STATUS=DONE
NEW_EVIDENCE=Process dies while task is DISPATCHED / STARTED. On restart, task has no result recorded. Heartbeat timeout reclaims task to QUEUED with attempts incremented.
PROVEN=Unfinished execution is detected via lease timeout and requeued.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_38
