# TASK_17 — READY → Worker Selection Trace

STATUS=DONE
NEW_EVIDENCE=source + physical

FILE_LINE_EVIDENCE=server/app.py:260-350 (POST /tasks/claim)

## Worker Selection Logic
1. Worker POSTs /tasks/claim with {worker_id, capabilities: [...]}
2. Server scans READY tasks
3. Matches task["target_capability"] against worker["capabilities"] list (string-in-list)
4. First match wins (no priority queue — first claimant wins)
5. Task transitions READY → DISPATCHED

## Capability Matching
mac capabilities: ["mac", "macos", "antigravity"]
Target "mac" → match YES (in list)
Target "macos" → match YES
Target "windows" → match NO (mac worker correctly excluded)

## Physical Evidence
Mac Worker PID 46250 claimed task-canary-B automatically after A reconciled.
WORKER_SELECTION_HUMAN_RELAY=0

PROVEN=Worker selection is capability-matched, first-claimant. Physical evidence confirmed.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_18
