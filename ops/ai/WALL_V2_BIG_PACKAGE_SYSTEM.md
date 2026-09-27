# Courier Wall V2 — Big-Package, Publish, Harvest

Status: ACTIVE WALL OPERATING MODEL
Supersedes the small-task WBUILD bootstrap for normal overnight work.

## Why V2

Small tasks caused workers to return too quickly and encouraged repeated setup/reads.
V2 uses large durable work packages, shared claims, one Harvester, and one Publisher.

100 logical slots do not mean 100 resident processes.
Use as many active motors as the host can sustain smoothly.

## Roles selected automatically

A worker running the universal V2 prompt chooses exactly one role:

1. PUBLISHER
   - only if unpublished durable ops/ai artifacts exist and publisher lock is free
   - publishes reusable wall/Ledger/queue truth to GitHub coordination branch
   - one publisher at a time

2. HARVESTER
   - only if unharvested package results exist and harvest lock is free
   - validates/deduplicates results
   - updates package state and unblocks dependencies

3. EXECUTOR
   - claims one READY BIG package
   - works through all package steps
   - does not return after one small subtask
   - after package completion claims the next READY package

4. PREPARER
   - only when current package generation is exhausted
   - creates a new generation from durable truth/results
   - never broad-scans the repo to invent work

## Durable local state

Windows:
C:\Users\lol\courier_work\wall_v2

Subdirectories:
- claims
- package_results
- checkpoints
- publish_queue
- published
- locks
- generations

## GitHub durability

Rules/specs/queues that should survive machines belong under ops/ai in GitHub.

Workers other than PUBLISHER do not commit coordination files concurrently.
They place publishable artifacts in publish_queue.

PUBLISHER serializes GitHub publication and records the resulting commit/ref in published metadata.

Application source is still owned by the explicit Central Writer.

## Cost law

- no broad repo scan
- no recursive repo census
- no repeated unchanged reads
- result reuse first
- exact-input reads only
- no idle analysis
- no duplicate review
- no long narrative output when a compact result works
- no source test suite unless the package explicitly requires a targeted test

## Large package rule

A BIG package should normally contain 4-12 concrete substeps and enough useful work for roughly 45-120 minutes when the required work exists.

A worker does not return after each substep.

Loop inside one package:
INPUTS -> SUBSTEP -> CHECKPOINT -> NEXT SUBSTEP -> PACKAGE RESULT

Then immediately claim another READY package.

## Truth resolution

The human is not a path resolver.

Resolve repo root with git rev-parse --show-toplevel.
Use stable indexes/pointers.
Use narrow Git path/history lookup only when needed.
Record TRUTH_CONFLICT rather than guessing.

## Session continuity

/clear, new provider session, machine restart, or manually authorized account change does not reset package completion.

New session:
read V2 system -> read current pointer -> resume durable package state.

## Resource admission

REQUESTED_LOGICAL_SLOTS may be 100.

ADMITTED_MOTORS is device-adaptive.
On the current single-host pattern, prefer a smooth small active pool over 100 simultaneous terminals.

Queue depth is capacity; resident windows are resource load.

## Completion

When no READY package exists:
- Harvester finishes outstanding results
- Publisher publishes outstanding durable artifacts
- one Preparer may create next generation
- otherwise truthful IDLE
