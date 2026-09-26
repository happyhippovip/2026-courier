# TASK_07 — Safest Isolated Canary 1 Workspace

STATUS=DONE
NEW_EVIDENCE=CONFIRMED (physical prior run complete)

## Canary Workspace
SAFE_CANARY_WORKSPACE=/Users/user/Downloads/courier_canary/
REASON=Fully isolated from production; separate repo checkout, separate state file, separate port

## Workspace Layout
/Users/user/Downloads/courier_canary/
├── artifacts/              Worker artifact drop zone
│   └── canary_A.txt        Physical artifact from prior A->VERIFY->B proof run
├── locks/                  Worker lock files
├── repo/                   Candidate checkout (synthesized: f7e1acb6 + 332a42f9)
│   └── server/app.py       Production app.py (original, not candidate-b-1)
│   └── run_canary.sh       Hermetic Canary run script
└── server/
    └── state/
        └── central_state.json  Canary state (task-canary-A: RECONCILED, task-canary-B: DISPATCHED)

## For Candidate-b-1 Canary
To use candidate-b-1 in courier_canary, checkout origin/candidate-b-1 into courier_canary/repo/
OR create new workspace: /Users/user/Downloads/courier_canary_b1/ (cleanest option)

## Port Assignment
PRODUCTION_PORT=8080 (PID 69407, do not touch)
CANARY_PORT=8081 (confirmed free)
BACKUP_PORT=18751 (free, confirmed)

PROVEN=courier_canary/ workspace physically isolated. Port 8081 free. Prior A->VERIFY->B succeeded here.
UNKNOWN=Whether courier_canary/repo should be updated to candidate-b-1 or new workspace created.
BLOCKER=None
NEXT=TASK_08
