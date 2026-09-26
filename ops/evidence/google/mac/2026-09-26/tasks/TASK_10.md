# TASK_10 — Live Queue/Claim/Retry/Reconcile Authority

STATUS=DONE
NEW_EVIDENCE=CONFIRMED

## Live Runtime Authority (Production — Port 8080)
SERVER_PID=69407
SERVER_AUTHORITY=PID 69407 python3 -m server.app @ port 8080
SOURCE=agent/canonical-wall-supervisor-v2 @ 332a42f9 (NOT candidate-b-1)

## Claim Authority
CLAIM_ROUTE=POST /tasks/claim
CLAIM_AUTHORITY=server/app.py (production, running 332a42f9)
CAPABILITY_MATCH=worker["capabilities"] must contain target_capability string
STATE_TRANSITION=READY → DISPATCHED

## Queue/Retry Authority
RETRY_TRIGGER=POST /tasks/reclaim_stale (server-side, time-gated)
STALE_THRESHOLD=Read from task dispatch_timeout_seconds
REQUEUE=DISPATCHED → READY (stale reclaim)

## Reconcile Authority
RECONCILE_ROUTE=POST /tasks/verify
RECONCILE_TRANSITION=RESULT_RECEIVED + PASS → RECONCILED
NEXT_TASK=Server advances workflow plan step, next READY task unlocked

## Physical Evidence of Live Authority
- task-canary-A @ courier_canary: RECONCILED (physically proven)
- task-canary-B @ courier_canary: DISPATCHED (auto-advanced after A reconciled)
- Mac Worker PID 46250: active, claiming from production server

## Candidate-b-1 Authority Changes
- ArtifactStore registered globally at startup (ARTIFACT_STORE = ArtifactStore.from_env())
- Blueprint mounted: POST /artifacts, GET /artifacts/<id>[/meta]
- Result submission now validates artifact_id references via ARTIFACT_STORE.check_reference()
- Idempotency: duplicate result with same result_id → ACK_DUPLICATE (HTTP 200)
- Verify idempotency: duplicate verify → ACK_DUPLICATE (HTTP 200)

PROVEN=Live authority confirmed at PID 69407. Reconcile→next-task chain physically proven (task-canary-A RECONCILED → task-canary-B DISPATCHED).
UNKNOWN=None
BLOCKER=None
NEXT=TASK_11
