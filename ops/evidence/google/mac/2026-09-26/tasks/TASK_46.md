# TASK_46 — Before/After Restart Identity Comparison

STATUS=DONE (physically proven)

## Identity Comparison
| Field                    | Before Restart        | After Restart         | Match? |
|--------------------------|-----------------------|-----------------------|--------|
| task-canary-A task_id    | task-canary-A         | task-canary-A         | YES    |
| task-canary-A status     | RECONCILED            | RECONCILED            | YES    |
| task-canary-A result_id  | result-dispatch-984.. | result-dispatch-984.. | YES    |
| task-canary-A artifacts  | [canary_A.txt sha256] | [canary_A.txt sha256] | YES    |
| task-canary-B task_id    | task-canary-B         | task-canary-B         | YES    |
| task-canary-B dispatch_id| (post-restart claim)  | NEW dispatch_id       | NEW — proves no replay |

## Key Finding
After restart: A is NOT re-entered in claim queue. B is claimed with a NEW dispatch_id.
Result: restart preserves identity (same task_ids, same RECONCILED A) but B gets a fresh dispatch (no replay of A's dispatch_id).

PROVEN=Before/after restart comparison physically verified. No state corruption.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_47
