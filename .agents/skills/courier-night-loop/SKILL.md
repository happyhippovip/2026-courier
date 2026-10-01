---
name: courier-night-loop
description: Run one bounded, read-only Courier Symphony night-queue work unit from durable state, then stop. Designed for Muse /loop so repeated wakes advance new work without duplicate prompt floods or child-agent fanout.
---

# Courier Night Loop

## Purpose

This skill is invoked repeatedly by Muse `/loop`.

Each invocation must do **new useful work only**.

It must never manufacture activity merely because another loop wake occurred.

## Hard safety

ONE AGENT ONLY.

Do not:
- start workflows;
- spawn child agents;
- spawn subagents;
- start background jobs;
- open extra terminals;
- create branches/worktrees;
- edit product source;
- commit/merge;
- run broad/full test suites;
- run provider actions;
- repeatedly poll;
- retry a failed resource probe.

If any operation reports:
- Too many open files
- EMFILE
- os error 24
- resource-pressure/spawn failure

then:
1. set `RESOURCE_PAUSE: YES` in state if possible;
2. perform no further shell/file probes this invocation;
3. return `COURIER_NIGHT_RESOURCE_PAUSE`.

## Durable local state

Use:

`/tmp/courier-v1/night-loop/STATE.md`

State contains:

```
EPOCH_HEAD:
RESOURCE_PAUSE:
COMPLETED_FINGERPRINTS:
WAITING:
BACKLOG:
LAST_UNIT:
NEXT_UNIT:
```

A fingerprint should be stable enough to avoid repeating the same review, for example:
`lane|file/function|risk/test-question|head`.

## Invocation algorithm

### 1. Read state

If state does not exist, initialize it.

If `RESOURCE_PAUSE: YES`, do not probe the host repeatedly. Return:
`COURIER_NIGHT_RESOURCE_PAUSE`.

### 2. Verify current truth cheaply

Verify CURRENT `integration/v1` and only the minimum current repo evidence needed.

Read canonical project rules if not already in session context:
- `AGENTS.md`
- `docs/V1_RULE_0.md`
- `docs/V1_PRODUCT_QUALITY_BAR.md`
- `docs/V1_ORCHESTRATION_PLAYBOOK.md`
- `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`
- `docs/NEXT_CHAT_HANDOFF.md`
- newest relevant Issue #54 rules
- `docs/v1/INTEGRATION_LOG.md`

Do not re-read the whole repo every wake.

### 3. New-head epoch

If CURRENT `integration/v1` differs from `EPOCH_HEAD`:
- start a new epoch for that head;
- keep old completed fingerprints as historical;
- inspect the delta and current critical path;
- generate a fresh prioritized backlog from evidence.

### 4. Refill backlog only when needed

If BACKLOG is empty, generate up to 12 evidence-backed read-only work units from CURRENT truth.

Priority order:

1. active critical-path implementation blockers;
2. failing/weak tests for existing V1 behavior;
3. restart/concurrency/corruption/process-safety risks;
4. Golden Path gaps;
5. Desktop Hub preparation tied to real journal/controller truth;
6. Windows EXE/clean-machine acceptance preparation;
7. diagnostics/privacy/power regression risks;
8. future adapter/mobile/overlay contracts only where preserving a boundary now prevents concrete rework.

Do not add a unit if its fingerprint is already completed for the same head.

Do not invent features.

### 5. Execute exactly one bounded work unit

Select the highest-priority first unfinished unit.

Spend the turn completing that unit thoroughly.

A unit may contain several sequential read-only substeps and targeted test-design checks.

Prefer depth over returning after one trivial observation.

For each unit record:

```
UNIT:
FINGERPRINT:
STATUS: DONE|REAL_BLOCKER|WAIT_FOR_LANE|DEFER_AFTER_EXE|SUPERSEDED
EVIDENCE:
FILES_FUNCTIONS:
FAILURE_CONSEQUENCE:
SMALLEST_TARGETED_TEST:
OWNER_LANE:
BLOCKS_STAGE:
FOLLOWUP:
```

Do not repeat completed fingerprints.

### 6. When there is no honest work

If, after a current-head refill, there is no new evidence-backed unit:
- do not create artificial technical debt;
- record `BACKLOG_EMPTY_AT_HEAD: <sha>`;
- return `COURIER_NIGHT_IDLE_NO_NEW_WORK`.

A future loop wake may cheaply check whether the head changed.

### 7. Stop

Each invocation performs one bounded unit and then stops.

Final line is one of:

`COURIER_NIGHT_UNIT_COMPLETE`
`COURIER_NIGHT_IDLE_NO_NEW_WORK`
`COURIER_NIGHT_RESOURCE_PAUSE`
