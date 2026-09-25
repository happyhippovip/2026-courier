# P3 cutover: server-owned artifact upload

`server/app.py` is read-only (P3). Everything else for artifact upload is in
place on this branch; the server needs the three-hunk patch in
`artifact-upload-cutover.patch`:

1. import `scripts.artifact_store`;
2. create the store (`COURIER_ARTIFACT_DIR`, default `server/state/artifacts`;
   `COURIER_ARTIFACT_MAX_BYTES`, default 16 MiB) and register its blueprint:
   `POST /artifacts` (worker key), `GET /artifacts/<id>` and
   `GET /artifacts/<id>/meta` (verifier key);
3. in `/tasks/result`, check every `artifact_id` reference against the stored,
   task-bound record (unknown id, other dispatch/attempt/worker, other name,
   hash or size -> 400).

The patch is exercised in a temporary copy by `tests/test_artifact_upload_flow.py`
(`tests/p3_preview.py`); `git apply --check` is part of that test.

Cutover order:

1. `git apply docs/p3/artifact-upload-cutover.patch` and restart the server.
2. Enable uploads on the workers: `COURIER_ARTIFACT_UPLOAD=1` (environment) or
   `"ARTIFACT_UPLOAD": true` in the worker config. Until then workers send
   path-only evidence, and the verifier fails Mac/Windows results instead of
   opening remote paths.
3. Run one Mac and one Windows canary and confirm `/tasks/verify` reaches
   `RECONCILED`.
