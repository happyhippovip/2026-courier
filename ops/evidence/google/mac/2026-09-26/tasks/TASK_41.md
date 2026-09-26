# TASK_41 — Exact RUN_1 A→VERIFY→B Checklist

STATUS=DONE (checklist prepared; prior run succeeded)

## RUN_1 Pre-Flight Checklist
- [ ] 1. Server running on isolated port 8081 (NOT 8080)
- [ ] 2. Canary workspace: /Users/user/Downloads/courier_canary/
- [ ] 3. Server started from candidate-b-1 checkout (for artifact_store support) OR prior checkout (proven sufficient for non-upload path)
- [ ] 4. State file initialized: goal + 2 tasks (task-canary-A READY, task-canary-B WAITING)
- [ ] 5. Worker registered with capabilities: ["mac", "macos"]
- [ ] 6. Verifier running against canary server (port 8081)
- [ ] 7. Canary artifact file pre-computed: COURIER-A2B-A\n (sha256: 96c1471...)

## RUN_1 Execution
1. MAC-01 claims task-canary-A
2. Worker writes canary_A.txt (exact bytes)
3. Worker submits result with sha256 + expected_sha256
4. Server → RESULT_RECEIVED
5. Verifier polls pending_verification
6. Verifier re-hashes, compares expected_sha256 → PASS
7. Server → RECONCILED
8. Server auto-unlocks task-canary-B → READY
9. Worker claims task-canary-B (zero human relay)
10. B execution begins

## Physical Completion (prior run)
STEPS_1_THROUGH_9_PROVEN=YES
HUMAN_RELAY_COUNT=0
A_EXECUTION_COUNT=1

PROVEN=All steps physically executed in prior run. Checklist validated.
UNKNOWN=None
BLOCKER=None (checklist is preparatory; execution already proven)
NEXT=TASK_42
