# TASK_37 — STARTED Ambiguity After Restart

STATUS=DONE
FILE_LINE_EVIDENCE=server/app.py:432 comment (candidate-b-1)

CURRENT_BEHAVIOR=STARTED tasks are quarantined after server restart. Server cannot know if execution completed.
PROTECTION=Tasks in STARTED state are NOT auto-reclaimed (unlike DISPATCHED stale reclaim).
RISK=MEDIUM — STARTED task is stuck until operator action. Replay risk if reclaimed without checking.
SAFE_FOR_CANARY_1=YES (Canary does not use STARTED state; result submitted immediately after execution)
DELIVERY_RETRY=N/A — STARTED is pre-result
EXECUTION_RETRY=REQUIRES manual operator resume/reclaim after safety check
UNKNOWN=Whether STARTED reclaim timeout is configurable in candidate-b-1.
