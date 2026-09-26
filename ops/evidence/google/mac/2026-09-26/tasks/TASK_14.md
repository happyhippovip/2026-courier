# TASK_14 — Verifier → Verification State Trace

STATUS=DONE
NEW_EVIDENCE=candidate-b-1 + physical prior run

FILE_LINE_EVIDENCE=scripts/courier_verifier.py:125-134 (verify_artifacts → verify_payload → POST /tasks/verify)

## Verification State Transition
STATE_BEFORE=RESULT_RECEIVED (task waiting for verification)
VERDICT_PASS=RECONCILED
VERDICT_FAIL=Task remains RESULT_RECEIVED, error logged, no retry triggered automatically

## Physical Evidence (prior Canary run)
PHYSICAL_TRANSITION_PROVEN=YES
- task-canary-A transitioned RESULT_RECEIVED → RECONCILED
- Server returned: {"status": "RECONCILED"}
- Verifier submitted matching result_id + artifacts → server accepted

## verify_payload structure
{result_id, artifacts: [{path, sha256, artifact_id (if candidate-b-1)}]}
POST /tasks/verify → server checks result_id match + artifacts match → RECONCILED

PROVEN=State transition RESULT_RECEIVED→RECONCILED physically proven on Mac.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_15
