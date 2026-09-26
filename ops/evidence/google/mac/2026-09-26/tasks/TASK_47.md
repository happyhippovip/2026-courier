# TASK_47 — Abort Conditions

STATUS=DONE

## Mandatory Abort Conditions for Canary Run

| Condition                                              | Action               |
|--------------------------------------------------------|----------------------|
| candidate-b-1 SHA changes after binding                | ABORT — identity broken |
| Runtime candidate mismatch (wrong app.py running)      | ABORT — restart with correct code |
| task-canary-A FAILED instead of RESULT_RECEIVED        | ABORT — diagnose before retry |
| task-canary-A re-executes (claimed twice)               | ABORT — replay protection breach |
| Manual result injection required (no worker claim)      | ABORT — not autonomous |
| task-canary-B requires manual start (no auto-claim)     | ABORT — not HUMAN_RELAY=0 |
| central_state.json unreadable/corrupt after restart     | ABORT — state integrity failure |
| expected_sha256 mismatch (wrong content verified)       | ABORT — content proof invalid |
| Verifier returns FAIL verdict for correct content       | ABORT — investigate before retry |
| Port collision (8081 occupied by production process)    | ABORT — use fallback port 18751 |

## Safe Conditions to Continue
- task-canary-A ACK_DUPLICATE on result re-POST → SAFE (idempotent, continue)
- task-canary-A RECONCILED persists after restart → SAFE (expected)
- Mac Worker poll delay → SAFE (wait up to 5 minutes for B auto-claim)

PROVEN=Abort conditions defined from physical run experience.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_48
