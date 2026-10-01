# Windows 8-Lane Return Protocol

This is the canonical Windows night map for the current eight interactive Muse/Antigravity windows.

## Core rule

Interactive windows are workers, not the 24h clock.

When a window returns to the prompt:
- do not restart its role;
- do not assign a second role;
- read the canonical WIN-XX checkpoint first;
- continue from NEXT EXACT TASK;
- if an existing /loop 10m is already active, do not create another loop;
- if the lane is genuinely idle, checkpoint and wait instead of inventing work.

The local Courier watchdog (PR #56) is the persistence layer. Returned chat windows are opportunistic compute lanes.

## Canonical WIN-01..WIN-08 map

### WIN-01 — Platform / Parity Lead
Mission:
- harvest WIN-02..WIN-08 checkpoints;
- maintain branch/worktree ownership map;
- resolve cross-lane collisions;
- decide integration order;
- keep commercial-readiness priorities synchronized with technical truth.

Default mode: read-mostly / coordinator.

### WIN-02 — Windows Worker Reliability
Mission:
- worker lifecycle;
- restart/recovery;
- exact process ownership;
- timeout/cancellation;
- cleanup;
- Windows path/environment/runtime reliability.

### WIN-03 — Process Tree / Timeout / Cancellation
Mission:
- child process trees;
- exact PID/identity handling;
- bounded termination;
- orphan/late process cleanup;
- regression tests.

Do not duplicate WIN-02 files without explicit handoff.

### WIN-04 — Schema / Path / Serialization Parity + Acceptance
Mission:
- Mac/Windows path parity;
- encoding/newlines/timestamps/temp paths;
- serialization/contracts;
- cross-machine acceptance tests;
- integration-contract verification.

Prefer read/test ownership over core implementation.

### WIN-05 — Zapier / Agent Integration Lead
Mission:
- productize Courier integration contracts for Zapier/agents;
- local/mock-first adapters;
- idempotency/auth/retry contract;
- define smallest sellable integration package.

No real customer webhooks, subscriptions, purchases or production activation without human approval.

### WIN-06 — Zapier Contract / Mock Tests
Mission:
- mock webhooks;
- malformed payloads;
- auth failures;
- duplicate delivery;
- idempotency;
- retry/failure tests;
- implementation-ready integration fixtures.

No production webhooks.

### WIN-07 — Lead / Growth Pipeline Verification
Mission:
- local lead schema;
- qualification/deduplication/scoring;
- CRM handoff contract;
- conversion instrumentation;
- synthetic fixtures;
- prepare a measurable, human-approvable outreach experiment.

No real outreach, ads, purchased leads, CRM production writes or publishing without human approval.

### WIN-08 — Revenue / Gains Verification
Mission:
- measure verified progress per euro and per wall-clock hour;
- cost per verified task;
- automation completion rate;
- failure/rework cost;
- lead qualification yield;
- integration/package value evidence;
- maintain an evidence-backed monetization experiment backlog.

No transactions, purchases, paid campaigns or trading.

## Commercial-readiness priority

The Windows group should optimize for the shortest evidence-backed path to a product that a human could choose to sell, not for artificial activity.

Priority:
1. reliability blockers that make the product unsafe/unreliable;
2. acceptance evidence proving the product works;
3. one clear Zapier/agent integration package;
4. one measurable lead/CRM workflow using synthetic/local data;
5. pricing/value evidence and a human-reviewable sales/experiment package;
6. only after explicit human approval: real external commercial actions.

No worker may claim revenue was created unless there is real external evidence. Local readiness, projected value, and hypotheses must be labeled separately.

## Return behavior

Every returned WIN-XX window should use this logic:

1. Read C:\tmp\courier-longrun\windows\WIN-XX\CHECKPOINT.md.
2. Re-read current HEAD/branch/worktree and current ownership.
3. If NEXT EXACT TASK is still valid and owned, execute it.
4. If completed/superseded, record that and pick the next evidence-backed role-local task.
5. Targeted verification only.
6. Checkpoint every meaningful unit.
7. Never stop merely because one unit completed.
8. Never create duplicate /loop schedules.
9. On EMFILE/resource/provider pressure, back off and checkpoint instead of retry storms.
10. If no real role-local work remains, wait; do not invent work.

## Operator shorthand

When reporting a returned window, use:
- "WIN1 zurück"
- "WIN2 zurück"
- ...
- "WIN8 zurück"

The Chief response should name:
- exact slot;
- exact role;
- exact next prompt;
- paste count;
- whether existing /loop remains untouched.
