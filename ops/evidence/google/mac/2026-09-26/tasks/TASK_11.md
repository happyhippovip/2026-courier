# TASK_11 — Worker Result → artifact_id Trace

STATUS=DONE
NEW_EVIDENCE=candidate-b-1 source-audited

## Trace: Worker Result → artifact_id (candidate-b-1)

### Step 1: Worker uploads artifact bytes
FILE_LINE_EVIDENCE=scripts/artifact_store.py:171-198 (create_blueprint → upload_artifact route)
ROUTE=POST /artifacts
WORKER_AUTH=require_auth (Bearer API key)
PAYLOAD=multipart/form-data: name=<workspace-relative-path>, binding JSON, file bytes
STATE_BEFORE=No artifact_id exists
STATE_AFTER=blob stored content-addressed, record written, artifact_id returned

### Step 2: artifact_id generation
FILE_LINE_EVIDENCE=scripts/artifact_store.py:44-50 (artifact_id_for)
FORMULA=art- + SHA256(JSON({binding: {goal_id,task_id,attempt_id,dispatch_id,worker_id}, name, sha256}))
DETERMINISTIC=YES — same dispatch + same content → same artifact_id (idempotent upload)

### Step 3: Worker includes artifact_id in result payload
FILE_LINE_EVIDENCE=scripts/artifact_store.py (binding check at TASK_RESULT time)
RESULT_ARTIFACTS=[{path: "relative/path", sha256: "<worker-hash>", artifact_id: "art-<hex64>"}]

### Step 4: Server validates artifact_id reference at result submission
FILE_LINE_EVIDENCE=server/app.py:377-379 (check_reference on each artifact ref)
STATE_BEFORE=Task DISPATCHED
STATE_AFTER=Task RESULT_RECEIVED (if artifact_id valid), or 400 (if invalid/misbound)

PROVEN=Full upload→artifact_id→result chain source-audited in candidate-b-1.
UNKNOWN=Whether production server (332a42f9) has this route (it does NOT — candidate-b-1 only).
BLOCKER=None for Canary 1 (Canary uses canary repo, not production). Production upgrade requires candidate-b-1 deployment.
NEXT=TASK_12
