# TASK_12 — artifact_id → Server-Side Artifact Trace

STATUS=DONE
NEW_EVIDENCE=candidate-b-1 source-audited

## Trace: artifact_id → Server-Side Artifact Bytes

FILE_LINE_EVIDENCE=scripts/artifact_store.py:200-218 (GET /artifacts/<id>/meta, GET /artifacts/<id>)
VERIFIER_AUTH=require_verifier_auth (separate API key)

### Record path
RECORD=server/state/artifacts/records/<artifact_id>.json
RECORD_CONTENTS={artifact_id, name, sha256, size, goal_id, task_id, attempt_id, dispatch_id, worker_id, stored_at}

### Blob path
BLOB=server/state/artifacts/blobs/<sha256[:2]>/<sha256>
CONTENT_ADDRESSED=YES — blob name IS the SHA-256; content is immutable once written

### Fetch flow
GET /artifacts/<id>/meta → returns record JSON
GET /artifacts/<id> → returns raw bytes (content-type application/octet-stream)
STATE_BEFORE=artifact_id in record store
STATE_AFTER=bytes served to verifier

UNKNOWN=Size limit (16MB default). Artifacts exceeding limit are rejected at upload time.
BLOCKER=None
NEXT=TASK_13
