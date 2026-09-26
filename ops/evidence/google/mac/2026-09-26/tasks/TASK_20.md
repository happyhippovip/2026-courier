# TASK_20 — RESULT_READY → RESULT_RECEIVED Trace

STATUS=DONE
FILE_LINE_EVIDENCE=server/app.py:352-415 (POST /tasks/result), scripts/courier_verifier.py:102 (poll pending_verification)

## Result Submission Flow
1. Worker POSTs /tasks/result with durable result payload
2. Server validates via validate_durable_result (9 required fields)
3. Server stores result in task["result"]
4. task["status"] = "RESULT_RECEIVED" (awaiting independent verification)
5. Server returns {"status": "RESULT_RECEIVED"}

## Idempotency (candidate-b-1)
FILE_LINE_EVIDENCE=server/app.py:368
Duplicate with same result_id → ACK_DUPLICATE (HTTP 200, no double-store)

## Verifier Poll
FILE_LINE_EVIDENCE=scripts/courier_verifier.py (GET /tasks/pending_verification loop)
Verifier polls GET /tasks/pending_verification → receives list of RESULT_RECEIVED tasks
Then fetches artifacts, verifies, POSTs /tasks/verify

## Physical Evidence
task-canary-A submitted → RESULT_RECEIVED → verifier polled → PASS → RECONCILED
HUMAN_RELAY_COUNT=0 at this transition

PROVEN=RESULT_RECEIVED→verification→RECONCILED physically proven. Zero human relay.
UNKNOWN=None
BLOCKER=None
NEXT=TASK_21
