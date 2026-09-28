# M197 — Zero-Byte Artifact Fail-Closed Boundary & Handling

## 1. Overview & Authority
- **Task ID**: M197
- **Area**: FAIL_CLOSED_ARTIFACT
- **Status**: COMPLETE

## 2. Fail-Closed Protocol
- Empty payload or zero-byte file (`size == 0`) is classified as unexecuted/aborted.
- Server returns HTTP 400 Bad Request if worker attempts zero-byte artifact registration.
- Verifier raises `EMPTY_ARTIFACT_EXCEPTION` and fails immediately.
