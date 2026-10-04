# Courier Symphony — Repeatable Queue Tokens

Status: **REUSABLE DEVELOPMENT ORCHESTRATION ASSET**

Purpose: support unattended work when an agent tends to return after a short turn.

The safe pattern is **not** "repeat the same analysis 65 times".
The safe pattern is:

> repeat the same **queue token**, where each invocation claims the first unfinished packet from a durable checkpoint and performs new work.

This prevents duplicate work while still allowing many queued inputs.

Read with:
- `docs/V1_ORCHESTRATION_PLAYBOOK.md`
- `docs/V1_WINDOW_CUSTODY_PROTOCOL.md`
- `docs/v1/orchestration/MUSE_MAC_LOW_FD_SINGLE_AGENT.md`

## 1. General queue-token invariant

Every invocation must:

1. read CURRENT repo state if needed;
2. read the queue checkpoint/ledger;
3. identify the FIRST packet not DONE/BLOCKED/WAITING;
4. work only that packet (or the bounded packet count named by the token);
5. persist the result;
6. stop;
7. never redo a completed packet.

If the queue/checkpoint cannot be read reliably, do not guess a packet number and do not duplicate work.

## 2. Antigravity repeatable 65-token

Use in **one Antigravity session** only when queued prompts execute serially.

Checkpoint/artifact:
`ANTIGRAVITY_COURIER_65_REVIEW`

Repeatable prompt:

```text
COURIER ANTIGRAVITY — NEXT PACKET TOKEN

Continue the existing ANTIGRAVITY_COURIER_65_REVIEW.

Do exactly ONE new packet.

1. Read the existing review/checkpoint and prior completed packet list.
2. Select the FIRST packet 01-65 not already marked:
   DONE / PROVEN / MISSING / CONTRADICTED / WAIT_FOR_L2 / DEFER_AFTER_EXE.
3. Re-verify only the CURRENT evidence required for that packet.
4. Perform the packet fully and append its result.
5. Update NEXT_PACKET.
6. Stop.

Never repeat a completed packet.
Never restart from packet 01.
Never spawn subagents.
Never edit product source.
Never create branches/commits/merges.
Never run broad suites.
If no packet remains, emit ANTIGRAVITY_65_COMPLETE and stop.
```

This token may be queued many times because each turn advances the same durable queue.

Do **not** use it if the provider executes queued messages concurrently rather than serially.

## 3. Muse Mac low-FD repeatable token

Use only in one retained Muse session.

Because the Mac has real EMFILE history, use ZERO child agents/workflows/subagents.

Checkpoint:
`/tmp/courier-v1/mac-low-fd/CHECKPOINT.md`

Repeatable prompt:

```text
COURIER MUSE LOW-FD — NEXT TWO PACKETS

Do not use workflow.
Do not use /goal.
Do not spawn child agents/subagents/background jobs.

Read:
/tmp/courier-v1/mac-low-fd/CHECKPOINT.md

Process the FIRST TWO queue packets not already marked:
DONE / BLOCKED_WITH_EVIDENCE / WAIT_FOR_L2.

For each:
- verify only required current evidence;
- complete the review;
- append evidence/result/owner/test/next packet;
- do not repeat prior work.

If fewer than two packets remain, finish the remainder.

If any operation returns:
Too many open files / EMFILE / os error 24 / resource-pressure spawn failure

then:
- write RESOURCE_PAUSE if possible;
- do not retry;
- stop immediately.

If all packets are accounted for, emit MAC_LOW_FD_QUEUE_COMPLETE.
```

Do not distribute this token across many Muse windows. Keep one owner session.

## 4. Claude/Opus writer relay

Do not queue independent overlapping writer prompts.

For one official writer lane, queued prompts may form **sequential phases** on the same branch/worktree.

Every phase must begin:
- inspect current diff/status/checkpoint;
- continue from first unfinished step;
- do not redo previous phase;
- remain within owned lane;
- commit/push only when the phase gate is satisfied.

Recommended L2 relay phases:
1. finish targeted controller/API tests;
2. adversarial restart/concurrency/corruption/SSE hardening;
3. full lane gate + race repetition + process smoke;
4. clean commit/push + L1-ready handoff.

If any phase discovers a real contract contradiction, stop later phases and report the contradiction instead of papering over it.

## 5. Host/resource rule

A queue may contain many **logical future turns** while only one turn is active.

Do not confuse:
- queue depth;
with:
- live local process count.

On Mac under heat/EMFILE evidence:
- one active Muse reviewer is preferred;
- Antigravity/Claude may continue if their execution path does not create additional local Muse child processes;
- close only windows proven safe by custody;
- do not add local parallelism merely to keep credits busy.

## 6. Morning harvest

After unattended work:
- inspect actual completed packet counts;
- trust evidence, not claimed runtime duration;
- deduplicate results;
- map actionable work to exactly one L1-L6 owner;
- update durable continuity only for real transitions.

Goal: maximize **new verified work per owner interaction**, not number of prompts sent.

## 7. Preferred replacement for huge manual Muse queues

When Muse supports `/loop`, do not manually enqueue the same token 30/65/100/1000 times.

Use the self-refilling project skill:

```
/loop 5m /courier-night-loop
```

The loop is serial: if a scheduled wake lands during an active run, Muse skips that occurrence rather than queueing it for later.

This gives effectively unbounded future wakes without an unbounded message backlog.

The skill still stops real work when:
- no evidence-backed task exists;
- RESOURCE_PAUSE is active;
- an owner decision is required.

That is intentional: infinite useful engineering cannot be guaranteed from a finite unchanged repo.
