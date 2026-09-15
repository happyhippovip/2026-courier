# Heavy Process Supervisor Design

## Purpose

Provide a durable, cross-process, fail-closed supervisor so Courier-controlled heavy work cannot run away, overlap, leak descendants, or destabilize the host.

This design complements:
- `docs/COMPUTE_RESOURCE_SAFETY_POLICY.md`
- `docs/HOST_OVERHEAT_INCIDENT_AND_RESUME_GATE.md`

Courier production remains blocked until the resume gate passes.

## Core design

Use two independent layers:

1. **Kernel-enforced cross-process lock**
   - Unix/macOS `fcntl.flock()` on a dedicated Courier lock file such as `runtime/resource_guard/heavy.lock`.
   - Acquire with `LOCK_EX | LOCK_NB` before any heavy process is spawned.
   - Keep the file descriptor open for the complete lifetime of the heavy job.
   - A second process that cannot acquire the lock must return `RESOURCE_GUARD_BUSY` before spawning anything.
   - The OS automatically releases the advisory lock if the owning supervisor process exits, which avoids a permanently stuck in-memory-only lock.

2. **Durable SQLite ownership ledger**
   - Store state in `runtime/resource_guard/heavy_jobs.sqlite3` using Python stdlib `sqlite3`.
   - Use an atomic write transaction such as `BEGIN IMMEDIATE` when claiming/updating the active ownership record.
   - Record mission identity, task hash, worker, owner PID, child PID, PGID/session, command fingerprint, start timestamp, deadline, retry number, state, TERM/KILL events, exit code, and cleanup result.
   - The ledger is evidence and crash-recovery metadata; the kernel file lock remains the primary mutual-exclusion primitive.

## Crash / stale-owner recovery

When a new supervisor successfully obtains the kernel lock but the ledger still says a prior job is `RUNNING`:

1. Treat it as an unclean previous execution.
2. Inspect only the recorded PID/PGID and recorded process identity.
3. Do not clear it based only on elapsed time.
4. If the exact recorded owned process group is still alive, block new heavy work and enter `ORPHAN_PROCESS_DETECTED` / `RESOURCE_GUARD`.
5. If the recorded process group is provably gone, mark the prior record `STALE_OWNER_RECOVERED` / `UNCLEAN_EXIT`, then allow a new claim.
6. Never use executable-name-only cleanup.

To reduce PID-reuse risk, ownership validation should combine PID/PGID with durable identity evidence such as command fingerprint and process start-time information available from local process inspection.

## Spawn contract

Every heavy subprocess must be created through the supervisor with:

- `stdin=subprocess.DEVNULL`
- `start_new_session=True`
- bounded stdout/stderr capture strategy
- finite requested timeout clamped to a global maximum ceiling
- exact mission/task/worker/retry metadata

The supervisor records the durable claim before spawn and records PID/PGID immediately after successful spawn.

If `Popen()` fails, the supervisor must write a terminal spawn-failure record, roll back/release its active ownership state, and release the file lock in `finally`.

## Timeout and cleanup contract

1. Wait/poll only with bounded intervals.
2. At deadline: record `TIMEOUT`.
3. Send `SIGTERM` only to the recorded Courier-owned PGID.
4. Wait a short bounded grace period.
5. Re-check the exact process group.
6. If still alive, send `SIGKILL` only to the same PGID.
7. Use a second bounded wait.
8. Re-scan the exact process group.
9. Record `CLEAN` or `ORPHANS_REMAIN`.
10. If `ORPHANS_REMAIN`, keep the system fail-closed and do not start another heavy job.

No `wait()` or `communicate()` call used in this path may be unbounded.

## Autonomous-loop containment

Heavy-process supervision alone is insufficient. Every autonomous loop must also have:

- maximum dispatch/step budget
- total wall-clock budget
- finite retry/cooldown budgets
- repeated-state fingerprint detection
- terminal fail-closed state when progress stops

The same planner/availability/error state may not revive work forever.

## Test execution policy

- Targeted tests first.
- No implicit fallback from targeted verification to full-suite discovery.
- Full regression requires explicit human approval and must itself run through the same heavy-process supervisor with a hard timeout.
- Only one heavy job may exist across all Courier processes.

## Required cross-process tests

1. Process A holds the file lock; Process B attempts heavy work and is rejected before spawn.
2. Process A crashes while a child group survives; Process B acquires the now-released kernel lock, reads the stale ledger, detects the still-live owned PGID, and fails closed.
3. Process A crashes after child exit but before ledger cleanup; Process B acquires the lock, proves the recorded group is gone, marks stale recovery, and proceeds safely.
4. A timeout sends TERM then bounded KILL only to the owned PGID.
5. An unrelated external process survives every cleanup test.
6. Spawn failure releases lock/ledger state.
7. No retry or founder-loop path can exceed explicit budgets.

## Canonical rule

`FLOCK ACQUIRE -> DURABLE CLAIM -> SPAWN OWNED SESSION -> BOUNDED EXECUTION -> TERM/KILL OWNED PGID -> VERIFY CLEAN -> DURABLE TERMINAL RECORD -> RELEASE LOCK`

If any ownership or cleanup proof is missing:

`FAIL_CLOSED / NO NEW HEAVY JOB`

## Current implementation boundary

`scripts/heavy_process_supervisor.py` is the canonical POSIX implementation.
It stores the lock and SQLite ledger under `runtime/resource_guard/`, exposes
an explicit future Windows adapter boundary, and does not implement Windows
Job Object support.

Relay subprocess stages use `run_relay_subprocess()` in
`scripts/run_chief_relay_cycle.py`; Night Supervisor propagates its session ID
as the supervisor owner. No planner, intake, queue, Customs, terminal-state,
or Windows-AI-OS behavior is changed.
