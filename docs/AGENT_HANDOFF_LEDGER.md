# Agent Handoff Ledger

`scripts/agent_handoff_ledger.py` maintains durable coordination metadata so a
new agent process can resume from an exact Git SHA without shared chat state.
It is **not** Courier runtime truth and has no scheduling, execution, dispatch,
verification, queue, Motor, or daemon authority.

## Format and transaction model

The ledger is one JSON bundle conforming to
`schemas/agent_handoff_ledger.schema.json`. It contains the current record,
schema version, optimistic revision, the non-authority declaration, and a
hash-chained audit entry for every revision. Keeping record and history in one
bundle prevents readers from observing a committed record without its history.
Each audit entry includes the complete record snapshot and its SHA-256 digest,
so every transition can be inspected and validated without reconstructing old
state.

Writers take a bounded advisory lock at `<ledger>.lock`, re-read and validate
the bundle under that lock, require the caller's expected revision, then write
a same-directory temporary file, flush and `fsync` it, atomically replace the
ledger, and `fsync` the directory where supported. Readers need no lock because
they see either the old or new complete file. Missing, corrupt, structurally
invalid, tampered, or history-inconsistent files fail closed.

The lock uses `fcntl.flock` on POSIX and `msvcrt.locking` on Windows. All ledger
writers must use this CLI; external editors are not coordinated writers and
will make chain validation fail if they alter the record without rebuilding
history. An orphaned lock file is harmless because ownership is held by the OS,
not by file existence.

## Commands

Create a complete record (all canonical uppercase fields are required):

```bash
python3 scripts/agent_handoff_ledger.py init path/to/ledger.json \
  --record path/to/record.json
```

Read canonical JSON or deterministic text:

```bash
python3 scripts/agent_handoff_ledger.py read path/to/ledger.json
python3 scripts/agent_handoff_ledger.py render path/to/ledger.json
python3 scripts/agent_handoff_ledger.py history path/to/ledger.json
```

Apply a partial update without replacing unrelated fields:

```bash
python3 scripts/agent_handoff_ledger.py update path/to/ledger.json \
  --expected-revision 0 \
  --updated-by session-b \
  --set 'STATUS=IN_PROGRESS' \
  --set 'TASKS_COMPLETED=7'
```

Values are parsed as JSON when possible, so arrays and `null` use JSON syntax.
A stale expected revision or busy lock exits nonzero without changing the
ledger. `CURRENT_SHA` must be a lowercase full 40-character Git SHA; `UNKNOWN`
is accepted only for revision-zero initialization and must be replaced before
the first update.

Give a new session only the ledger path, then retrieve its self-contained work:

```bash
python3 scripts/agent_handoff_ledger.py next-action path/to/ledger.json
```

The output includes `NEXT_EXECUTABLE_ACTION`, blocker and owner, exact SHA,
branch, runtime identity, status, continuation checkpoint, revision, and the
non-authority declaration.

## Secret boundary

The record accepts exactly the documented canonical fields. It rejects likely
credential field names and values including passwords, authorization headers,
API keys, access/refresh tokens, private keys, and common token prefixes.
Store durable evidence as `https://` URLs, never embedded credentials.

## Tracked example

`examples/agent_handoff_ledger.json` is a coordination-only snapshot generated
with the CLI from durable Issue #37 evidence. Unknown counters remain `null`;
the example does not upgrade an Issue report into observed runtime truth or
supersede canonical Courier state.
