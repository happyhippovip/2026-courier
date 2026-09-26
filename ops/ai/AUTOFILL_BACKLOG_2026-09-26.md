# Courier Autofill Backlog Seed — 2026-09-26

This branch is **coordination-only** so it does not disturb the live Mac or Windows writer branches.

## Goal

Eliminate manual prompt refilling.

Canonical target:

`QUEUE -> CLAIM -> RESOURCE ADMIT -> START WORKER -> RESULT -> VERIFY -> NEXT`

The human must not relay prompts between workers.

## Runtime shape

- 64 **logical** slots: 32 Mac + 32 Windows.
- Logical slot count does not equal active heavy-process count.
- Mac starts with max 1 heavy task.
- Windows starts with max 2 heavy tasks until measured evidence justifies more.
- Exactly one scheduling authority.
- Exactly one writer per `write_scope`.
- Read-only/research work may run in parallel when resource-safe.
- Backlog should scale to 100/1000 tasks without proportional processes.

## Current bottleneck this seed addresses

Some interactive Muse windows finish and return to a prompt because nothing durable assigns the next task. The fix is not more copy/paste; the fix is a canonical replenisher/dispatcher plus programmatic worker adapter and persisted results.

## Queue seed

Machine-readable tasks live in:

`ops/ai/AUTOFILL_TASK_SEED_2026-09-26.json`

The seed contains 30 work items covering:

- canonical scheduler audit
- Muse programmatic adapter
- slot lifecycle and rate-limit handling
- auto-next
- result idempotency and ambiguous recovery
- process leases / owned stop
- independent Mac/Windows resource governors
- 64-slot registry
- two-host registration and atomic claims
- writer-scope locking and worktree isolation
- result collection / backlog dedupe
- 1000-task queue scale proof
- one-command Mac/Windows bootstrap
- wrong-host guard
- Antigravity setup verifier
- Wall status projection
- canary 1->4
- restart recovery
- idle efficiency
- final Opus integration gate

## Important

This is a backlog seed, **not proof that any listed bug exists**. Audit/test tasks must gather evidence before a write task is dispatched.

Do not modify:

- `server/app.py`
- `server/run_waitress.py`
- `server/launch_server_hidden.vbs`

unless a future explicit ownership transfer authorizes it.

No main push, force-push, broad cleanup, account rotation, or GitHub Actions for local checks.
