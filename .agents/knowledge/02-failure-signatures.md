# Failure Signatures

- `426 Upgrade Required`: Worker submitted a `runtime_sha` that mismatches `SERVER_SHA`. Indicates a stale worker that must be killed/updated.
- `409 CONFLICT`: Worker submitted a duplicate or contradictory result for an already finalized task. Idempotent marker logic safely absorbs this.
- `403 Forbidden` (Worker Mismatch): A worker attempted to post a result for a task bound to a different `worker_id`. Identity spoofing block.
- `AMBIGUOUS_CRASH`: Daemon output when `effect_marker.json` is discovered on boot. Proves the process died before `result_marker.json` could be written.
- `Found unsent result marker`: Daemon output indicating a network failure occurred *after* the task finished but *before* the server acknowledged the HTTP 200.
