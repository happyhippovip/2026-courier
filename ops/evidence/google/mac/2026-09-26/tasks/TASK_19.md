# TASK_19 — Dispatch → STARTED Trace

STATUS=DONE
FILE_LINE_EVIDENCE=scripts/mac_worker/daemon.py (task execution loop)

## STARTED Semantics
After claim, worker begins executing the task.
In production mac_worker daemon: execution happens in subprocess.
STARTED status: set by worker marking execution begun (not a server-side route in base 332a42f9).
NOTE: In candidate-b-1 server.app.py, STARTED is a valid task state for recovery semantics.

## STARTED Recovery (candidate-b-1)
FILE_LINE_EVIDENCE=server/app.py:432 (STARTED ambiguity comment)
If task is STARTED and server restarts: cannot know if execution completed.
Replay would risk duplicate effect.
Recovery: STARTED tasks are quarantined (not auto-reclaimed) to avoid replay.

## Physical Evidence
In Canary run: claim → execution → result submission (no STARTED intermediate exposed).
Production mac_worker daemon claims and executes synchronously.

PROVEN=DISPATCHED→execution is physical. STARTED recovery semantics source-audited.
UNKNOWN=Whether mac_worker/daemon.py emits STARTED heartbeat (not observed in canary run).
BLOCKER=None
NEXT=TASK_20
