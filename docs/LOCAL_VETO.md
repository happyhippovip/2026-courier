# Local host veto

A host may refuse a work item before it accepts the item. The refusal is local
to that host. The item goes back to the queue for a different host. It is not
recorded as a failed result.

## Decision

`evaluate` returns one of:

- `ACCEPT`
- `VETO(reason_code, detail)`

The same item, config, governor health, and clock always produce the same
decision. Rules are checked in this order and the first match wins:

| Order | Reason code | When |
|---|---|---|
| 1 | `config_unreadable` | Host config, the protected-paths file, quiet hours, or governor health cannot be read |
| 2 | `user_pause` | The configured pause file is present |
| 3 | `resource_pause` | Governor read-only health is `RESOURCE_PAUSE` |
| 4 | `provider_unavailable` | The item names a provider that is not installed or not logged in |
| 5 | `protected_path` | `files_scope` touches a path listed in the protected-paths file |
| 6 | `quiet_hours` | The clock is inside the configured quiet-hours window |

If none match, the decision is `ACCEPT`.

## Host config

One JSON object:

```json
{
  "pause_file": "/var/lib/courier/PAUSE",
  "protected_paths_file": "/var/lib/courier/protected-paths.txt",
  "quiet_hours": {"start": "22:00", "end": "07:00", "tz": "UTC"},
  "providers": {
    "codex": {"installed": true, "logged_in": true}
  }
}
```

The protected-paths file is one path per line. Blank lines and lines that start
with `#` are ignored. A scope path touches a protected path when the two are
equal or one is inside the other. `secret` does not match `secret-notes`.

Quiet hours use `HH:MM` in UTC. The start minute is inside the window and the
end minute is outside it. When the end is earlier than the start, the window
crosses midnight. Equal start and end means there is no window.

A missing file, a directory, invalid JSON, or a malformed field is
`config_unreadable`. The host does not accept the item.

## Governor

Health is read from `health()` when that method exists, otherwise from the
`state` attribute. The only pause value is the string `RESOURCE_PAUSE`.

This check does not call `admit_job`, `measure_pressure`, `trigger_quiesce`,
`read_metrics`, or `classify`, and it does not change governor state.

## Receipt

A veto writes `local-veto-<dispatch_id>.json`:

- `schema`: `courier.local_veto.v1`
- `decision`: `VETO`
- `reason_code`, `detail`
- `dispatch_id`, `task_id`, `worker_id`
- `path_hashes`: `sha256:` digests of the normalized paths that mattered
- `recorded_at`: UTC timestamp

The file does not contain secrets, tokens, or full local paths. An accepted
item does not write a receipt.

## Queue

`consider(queue, worker_id, ...)` returns `(verdict, item)`. It asks the queue
for one item (`claim`). On `ACCEPT`, `item` is the one the host keeps. On
`VETO`, the receipt is written, the item is returned (`release`), and `item`
is `None`. `release` does not fail the item. An empty queue is
`(ACCEPT, None)`.

## Boundary

Adapter registration and the resource governor stay in their own code. This
module only decides and records. The host calls `consider` once, after it
receives an item and before it accepts that item.
