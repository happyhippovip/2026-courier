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

1. `git apply docs/p3/artifact-upload-cutover.patch`, then
   `git apply docs/p3/server-idempotency-cutover.patch` (it applies on top of the
   first), and restart the server.
2. Enable uploads on the workers: `COURIER_ARTIFACT_UPLOAD=1` (environment) or
   `"ARTIFACT_UPLOAD": true` in the worker config. Until then workers send
   path-only evidence, and the verifier fails Mac/Windows results instead of
   opening remote paths.
3. Run one Mac and one Windows canary and confirm `/tasks/verify` reaches
   `RECONCILED`.

## Second patch: result idempotency and verification (Cannon V1)

`server-idempotency-cutover.patch` carries the server fixes from
`claude/keen-gates-8miu4n`:

1. `/tasks/result`: a resend of the stored result (same `dispatch_id`,
   `result_id`, `status`) is answered `ACK_DUPLICATE`, also after a failed
   result requeued the task; a different result for a processed task is `409`.
   Before, both were answered `IGNORED` with `200`, so a conflicting result was
   dropped silently.
2. `/tasks/verify` mirrors its outcome into the workflow step, so
   `FAILED_VERIFICATION` can be resumed; `resume` with `retry` requeues the task
   and the next claim mints a new attempt/dispatch identity.
3. `resume` with `force_success` is refused. It used to mark a step
   `RESULT_RECEIVED` without a DurableResult or verifier, using the worker key.
4. The `__main__` guard moves to the end of the file, so `resume` is registered
   when the server is started as `python3 server/app.py`.
5. `/workers/unregister` is sticky: heartbeats no longer return the worker to
   service; only `/workers/register` does.

Exercised in a temp copy by `tests/test_p3_server_idempotency.py`.
