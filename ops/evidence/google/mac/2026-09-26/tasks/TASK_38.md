# TASK_38: Duplicate / Retry: FAILED -> Requeue Behavior

STATUS=DONE
NEW_EVIDENCE=Task result posted with status FAILED. Server checks attempts: if attempts < MAX_ATTEMPTS (3), task is requeued as QUEUED. If attempts >= 3, status becomes FAILED_TERMINAL.
PROVEN=Bounded retry loop (max 3) prevents infinite failure churn.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_39
