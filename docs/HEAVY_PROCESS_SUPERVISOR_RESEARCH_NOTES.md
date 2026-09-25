# Heavy Process Supervisor Research Notes

These notes capture external-reference-backed implementation guidance for the Courier host-safety fix.

## Cross-process exclusion

On macOS/Unix, Python's standard-library `fcntl.flock()` provides an advisory file lock on an open file descriptor. A non-blocking exclusive lock (`LOCK_EX | LOCK_NB`) is suitable as a kernel-enforced single-heavy-job gate across separate Courier processes.

Recommended pattern:
- open `runtime/resource_guard/heavy.lock`
- attempt non-blocking exclusive `flock`
- if busy: return `RESOURCE_GUARD_BUSY` before any spawn
- keep the file descriptor open for the full job lifetime
- release in `finally`

## Durable metadata

Use stdlib `sqlite3` for the durable ownership ledger. SQLite `BEGIN IMMEDIATE` starts a write transaction immediately and fails with a busy condition if another writer already holds the write transaction. Use this for atomic claim/update operations, while the kernel file lock remains the primary single-heavy-job exclusion mechanism.

## Subprocess contract

Python's subprocess APIs support:
- `stdin=subprocess.DEVNULL`
- finite `timeout=` values
- `Popen.communicate(timeout=...)`
- `Popen.wait(timeout=...)`

A timeout from `communicate()` does not itself guarantee a child is cleaned up in custom Popen workflows, so Courier must explicitly terminate its exact owned process group, complete bounded cleanup, and verify the group is gone.

## Process-group cleanup

On Unix/macOS, Python exposes `os.killpg(pgid, signal)` to signal a specific process group. Courier should create each heavy subprocess in a new session/process group and later signal only that recorded PGID. Broad name-based process killing is forbidden.

## Durable safety principle

A robust architecture uses all of these together:

1. kernel file lock for cross-process exclusion,
2. durable SQLite ledger for ownership/recovery evidence,
3. new process session/group for exact descendant containment,
4. finite global timeout ceilings,
5. TERM -> bounded wait -> KILL -> bounded wait -> re-scan,
6. bounded autonomous-loop/retry budgets,
7. fail-closed stale-owner/orphan recovery.
