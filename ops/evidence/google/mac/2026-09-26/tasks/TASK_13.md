# TASK_13 — Artifact → Verifier Trace

STATUS=DONE
NEW_EVIDENCE=candidate-b-1 source-audited

## Trace: Artifact → Verifier

FILE_LINE_EVIDENCE=scripts/courier_verifier.py:43-50 (fetch_artifact)

### Verifier fetch
fetch_artifact(artifact_id):
  1. GET /artifacts/<id>/meta  → record
  2. GET /artifacts/<id>       → data bytes
  If size > DEFAULT_MAX_BYTES: raises ValueError

### Independent hash (candidate-b-1 key feature)
FILE_LINE_EVIDENCE=scripts/courier_verifier.py:54-85 (verify_artifacts)
server_hash = hashlib.sha256(data).hexdigest()  ← computed from SERVER-STORED bytes, not worker-reported

### expected_sha256 check
FILE_LINE_EVIDENCE=scripts/courier_verifier.py:74-76
if "expected_sha256" in art:
    if hashlib.sha256(data).hexdigest() != art["expected_sha256"]:
        log("Hash mismatch against expected_sha256 for {path}")
        return FAIL

### verify_uploaded_artifact check
FILE_LINE_EVIDENCE=scripts/artifact_store.py:147-160
Checks: sha256 match, binding match (goal_id/task_id/attempt_id/dispatch_id/worker_id), name match

STATE_BEFORE=artifact_id in result["artifacts"]
STATE_AFTER=PASS (all hashes match, binding valid) or FAIL (any mismatch)

PROVEN=Verifier independently re-hashes server-stored bytes. Worker-reported sha256 alone cannot produce PASS (Task 26 confirmed).
UNKNOWN=None
BLOCKER=None
NEXT=TASK_14
