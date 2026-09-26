# Courier Fast-Track 48H Mode — 2026-09-26

Status: Product/preparation concept. Does not override current Core gate order.

## Short answer

Courier needs a deadline mode for users who only have one or two days left in a provider allowance, trial, project window, travel window, machine-access window, or other limited period.

The goal is **not to waste tokens quickly**. The goal is to convert remaining time/allowance into the maximum amount of verified useful work before the deadline.

Working name:

`FAST_TRACK_48H`

## User promise

"I only have 1–2 days. Use the remaining capacity on the most valuable safe work, keep evidence, and leave me with a resumable result."

## Core behavior

A Fast-Track run receives:

- deadline / remaining time window;
- provider/model availability;
- optional token/credit budget where observable;
- allowed machines/hosts;
- Goal Contract;
- write scopes;
- forbidden scopes;
- required evidence;
- human/money/safety gates.

Courier then:

1. identifies the critical path;
2. creates a large durable queue of bounded tasks;
3. separates writers from reviewers;
4. parallelizes only independent work;
5. reuses existing evidence before spending model capacity;
6. assigns expensive models only to decision-critical work;
7. assigns cheaper/free capacity to read-only audits, fixtures, inventories and evidence maps;
8. snapshots state continuously;
9. checkpoints useful partial results before the deadline;
10. stops generating work when only duplicate/busywork remains.

## Scheduling objective

Optimize for:

`VERIFIED_VALUE_PER_REMAINING_HOUR`

and where measurable:

`VERIFIED_VALUE_PER_REMAINING_TOKEN`

Not:

`TOKENS_BURNED`

A run that spends fewer tokens but closes the critical gate is better than a run that empties an allowance with duplicate analysis.

## Work classes

### P0 — deadline blockers

Work without which the main goal cannot advance.

### P1 — proof and recovery

Tests, candidate binding, restart evidence, deterministic fixtures, duplicate/replay safety.

### P2 — reusable preparation

Portability audits, evidence maps, pilot preparation, documentation that directly reduces later work.

### P3 — reserve

Useful independent tasks that may be pulled only when P0–P2 capacity is saturated.

### SKIP

Duplicate architecture, speculative features, repeated summaries, broad test fanout without causal value, idle model chatter.

## Concurrency law

Logical queue size may be large.

Physical active work stays bounded by:

- machine resources;
- provider authorization;
- write-scope conflicts;
- rate limits;
- account terms;
- human safety/permission gates.

No quota circumvention, account rotation, or hidden provider bypass.

## Token/credit handling

When a provider exposes remaining allowance, Courier may use it as a planning signal.

It must not:

- fabricate remaining-token numbers;
- evade provider limits;
- rotate accounts to bypass restrictions;
- keep models busy only to consume allowance.

It should:

- front-load high-value tasks;
- checkpoint early and often;
- prefer deterministic/local work where models add no value;
- preserve an explicit final review reserve for the last integration decision;
- leave a resumable evidence bundle even if capacity expires.

## 48-hour default cadence

### T-48h to T-24h

- bind candidate/state;
- create durable queue;
- parallel read-only/prep work;
- close deterministic gaps;
- preserve one source writer per mutable scope.

### T-24h to T-6h

- converge reports;
- run targeted tests;
- close first causal blockers;
- prepare physical proof;
- reduce speculative work.

### T-6h to T-1h

- freeze scope;
- use strongest reviewer(s) on the actual candidate;
- perform physical acceptance/restart proof if authorized;
- snapshot evidence.

### Final hour

- no architecture expansion;
- no optional feature work;
- package exact state, SHA, test evidence, blockers and next action;
- make restart/resume possible on another day/provider.

## Required durable outputs

Every Fast-Track run should end with:

- CURRENT_GOAL.md
- CANDIDATE_BINDING.md
- QUEUE_STATUS.md
- EVIDENCE_INDEX.md
- BLOCKERS.md
- LAST_CRITICAL_SNAPSHOT.md
- RESUME_NEXT_ACTION.md

## Product boundary

FAST_TRACK_48H is an execution policy layered on Courier's existing Goal Contract, Ledger, Motor, evidence and recovery model.

It is **not** permission to bypass earlier product gates or safety boundaries.
