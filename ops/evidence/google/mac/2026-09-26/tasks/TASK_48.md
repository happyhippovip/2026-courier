# TASK_48 — Minimum Evidence Pack

STATUS=DONE

## Required Evidence Pack (Canary 1)

| File                                          | Purpose                                    | Required |
|-----------------------------------------------|--------------------------------------------|----------|
| GOOGLE_CLI_A_VERIFY_B_RUNTIME_EVIDENCE.json   | Full A→VERIFY→B hermetic run transcript    | YES      |
| GOOGLE_CLI_RESTART_REPLAY_EVIDENCE.md         | Restart + no-A-replay proof                | YES      |
| GOOGLE_CLI_PHYSICAL_RUNTIME_AND_BINDING_CARD.md | Process PIDs, ports, SHA, Muse version | YES      |
| CLI5_VISIBLE_PROOF.md                         | Human-readable visible proof summary       | YES      |
| central_state.json (canary)                   | task-canary-A=RECONCILED, B=DISPATCHED     | YES      |
| canary_A.txt sha256 physical hash             | 96c1471cc2dfc... (computed on disk)        | YES      |

## Already Present
All 6 evidence files exist at /Users/user/Downloads/courier_work/google_longrun/reports/.

## Excluded
- Giant server logs (not required)
- Full process stdout dumps (not required)
- Intermediate state snapshots (not required unless restart checkpoint)

PROVEN=Evidence pack complete and physically present.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_49
