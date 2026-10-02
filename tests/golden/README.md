# Courier v1 golden acceptance harness (owned by L1)

These tests are the merge gate for lanes L2–L6. Each one is **skipped with an
explicit reason** until the v1 modules it drives exist:
`courier_core.serve`, `courier_core.journal`, `courier_core.projection`,
`courier_worker.host` and `adapters.synthetic`. Once those modules exist, every
assertion runs. Nothing here is xfailed or disabled.

The harness drives real processes. It talks to them only through the
interfaces below, which are the binding contract (architecture contract E/F).
A lane that needs any of this to change must ask L1 to change the harness.

## Processes

| Process | Command (cwd = repo root, `PYTHONPATH` = repo root) |
|---|---|
| Controller | `python -m courier_core.serve --home <H> --port <P> --print-port` |
| Worker host | `python -m courier_worker.host --home <H> --controller http://127.0.0.1:<P> --max-tasks 1 --heartbeat 2` |

- `COURIER_HOME=<H>` is also set in the environment of both processes.
- The controller binds `127.0.0.1` only.
- **Graceful stop of the controller:** `POST /v1/shutdown`. The process must exit within 10 s.
- **Graceful stop of the worker host:** `SIGTERM` on POSIX. On Windows, `CTRL_BREAK_EVENT`; the host is started with `CREATE_NEW_PROCESS_GROUP`. The host must finish or abandon its current work cleanly, flush its outbox and exit within 10 s, leaving no child processes.
- **Hard kill (crash simulation):** `Popen.kill()`. After a new worker host starts on the same home, no child process of the killed host may survive, whether the Job Object or the orphan gate takes care of it.

## Files under `<H>`

| Path | Meaning |
|---|---|
| `<H>/courier.db` | SQLite journal. Table `events(seq, event_id, schema_v, type, task_id, attempt, dispatch_id, worker_id, result_id, dedupe_key, ts_utc, payload, prev_hash, hash)`; `payload` is JSON text |
| `<H>/run/controller.token` | Per-install API token written by the controller. Every request sends it as header `X-Courier-Token` |
| `<H>/outbox/**` | Worker outbox. It must be empty after a clean shutdown |

## HTTP API used by the harness (prefix `/v1`)

| Call | Request | Expected response |
|---|---|---|
| `GET /health` | – | `{"mode": "normal" \| "degraded_readonly", "head_seq": int, ...}`. When degraded, it also includes `"first_bad_seq": int` |
| `POST /tasks` | `{"adapter": "synthetic", "params": {...}, "effect_class": "idempotent" \| "non_idempotent", "max_attempts": int, "lease_ttl_s": int, "timeout_s": int?}` | `200`/`201` `{"task_id": str}`; `503` when degraded |
| `POST /claim` | `{"worker_id": str}` | `200` `{"task_id", "attempt", "dispatch_id", "ttl_s", "spec"}`, or `204` if there is no work |
| `POST /start` | `{"dispatch_id": str}` | `200` |
| `POST /heartbeat` | `{"worker_id": str, "dispatch_ids": [str]}` | `200` |
| `POST /result` | `{"dispatch_id", "result_id", "artifacts": [{"path", "sha256"}], "outcome": "success" \| "failure"}` | `200` `{"status": "ACCEPTED_FOR_VERIFY" \| "ACK_DUPLICATE"}`; `409` for a stale or superseded dispatch |
| `POST /tasks/<id>/cancel` | – | `200` |
| `GET /events` | header `Last-Event-ID: <seq>` | SSE; every journal event is sent with `id: <seq>` |
| `POST /shutdown` | – | `200`, then the process exits |

## In-process functions used by the harness

These are called only on a **copy** of the database, never on the live file, so the controller stays the only writer.

- `courier_core.journal.Journal(path)`, with `.open()` and `.verify_chain()`; the result has `.ok`.
- `courier_core.projection.projection_hash(conn)` and `rebuild(journal, out_path)`.

## Synthetic adapter parameters (`adapters/synthetic.py`, L4)

| Parameter | Default | Meaning |
|---|---|---|
| `sleep_s` | 1 | Runtime before writing the artifact |
| `write` | `out.txt` | Artifact file name |
| `content` | `courier-golden` | Artifact content |
| `crash_after_s` | null | The task process exits with a non-zero status after this many seconds |
| `hang` | false | The task never finishes on its own |
| `fail_transient_n` | 0 | Attempts `1..n` report a retryable failure |
| `fault_attempts` | `[1]` | Attempts on which `crash_after_s` and `hang` apply |

## Event sequence of the golden path

`TASK_CREATED → TASK_CLAIMED → TASK_STARTED → RESULT_READY → RESULT_ACCEPTED → TASK_COMPLETE`

`TASK_PROGRESS` events may appear and are ignored by the sequence assertion.
