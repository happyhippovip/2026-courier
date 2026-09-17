# Agent Handoff Ledger

`scripts/agent_handoff_ledger.py` maintains durable coordination metadata so a
new agent process can resume from an exact Git SHA without shared chat state.
It is **not** Courier runtime truth and has no scheduling, execution, dispatch,
verification, queue, Motor, or daemon authority.

## Format and transaction model

The ledger is one JSON bundle conforming to
`schemas/agent_handoff_ledger.schema.json`. It contains the current record,
schema version, optimistic revision, a versioned acceptance guard, the
non-authority declaration, and a hash-chained audit entry for every revision.
Keeping record, guard, and history in one bundle prevents readers from
observing a committed transition without its evidence decision.
Each audit entry includes the complete record snapshot and its SHA-256 digest,
and schema-version-2 entries also include the complete guard snapshot and
combined state digest. Existing schema-version-1 history entries remain
byte-for-byte preserved when the first guarded update upgrades a ledger.

The guard records:

- evidence source URL/type, observation time, exact SHA/runtime binding,
  validity, and reason;
- acceptance predicate name/version and every required predicate result;
- `PROVISIONAL` or `CANONICAL_ACCEPTED` transition state;
- `WORKER_STATE`; and
- the explicit flow `EXECUTION -> EVIDENCE -> ACCEPTANCE_GUARD ->
  LEDGER_TRANSITION -> NEXT_EXECUTABLE_ACTION`.

`CANONICAL_ACCEPTED` fails validation unless every required predicate is
`PASS`, every PASS cites evidence in the guard, and that evidence is `VALID`
and bound to the exact current SHA and runtime identity. Issue closure or a
narrative PASS can therefore be stored as provenance without becoming runtime
acceptance.

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
  --record path/to/record.json \
  --guard path/to/acceptance-guard.json
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
  --guard path/to/replacement-guard.json \
  --set 'STATUS=IN_PROGRESS' \
  --set 'TASKS_COMPLETED=7'
```

Values are parsed as JSON when possible, so arrays and `null` use JSON syntax.
A stale expected revision or busy lock exits nonzero without changing the
ledger. `CURRENT_SHA` must be a lowercase full 40-character Git SHA; `UNKNOWN`
is accepted only for revision-zero initialization and must be replaced before
the first update. A schema-version-1 ledger requires `--guard` on its next
update; that atomic update advances the format to schema version 2.

Before trusting a checkpoint, compare it with explicit authoritative
observations. The core CLI performs no network calls:

```bash
python3 scripts/agent_handoff_ledger.py freshness path/to/ledger.json \
  --observed-branch release-candidate-integration \
  --observed-sha 0123456789abcdef0123456789abcdef01234567 \
  --observed-issue-state CLOSED \
  --observed-evidence-url https://github.com/owner/repo/issues/37
```

Staleness exits `3` and returns machine-readable reasons with
`NEXT_ACTION_ALLOWED=false`. Legacy unguarded ledgers are stale by definition.
Missing guard state also makes `next-action` exit nonzero, preventing an old
completed-work instruction from reaching a foreign session.

Give a new session only the ledger path, then retrieve its self-contained work:

```bash
python3 scripts/agent_handoff_ledger.py next-action path/to/ledger.json
```

The output includes `NEXT_EXECUTABLE_ACTION`, blocker and owner, exact SHA,
branch, runtime identity, status, continuation checkpoint, revision, and the
non-authority declaration. It also includes transition state, worker state,
flow, and the complete versioned acceptance predicate. A `PROVISIONAL`
transition may direct Session B only to the recorded validation blocker; it
does not claim canonical acceptance.

## Secret boundary

The record accepts exactly the documented canonical fields. It rejects likely
credential field names and values including passwords, authorization headers,
API keys, access/refresh tokens, private keys, and common token prefixes.
Store durable evidence as `https://` URLs, never embedded credentials.

## Tracked example

`examples/agent_handoff_ledger.json` is a coordination-only snapshot generated
with the CLI from current PR #39 and closed Issue #37 evidence. Unknown runtime
properties and counters remain `UNKNOWN`/`null`; the transition remains
`PROVISIONAL` until machine-verifiable evidence is bound to the exact release
SHA/runtime and every required predicate passes. The example does not upgrade
an Issue report into observed runtime truth or supersede canonical Courier
state.
