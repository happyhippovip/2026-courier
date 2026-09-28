# Courier Overnight Autonomy Protocol — CURRENT

Status: DURABLE OPERATING RULE
Date: 2026-09-28

## Goal
Let Courier workers make useful progress for hours without requiring the founder to refill windows, while avoiding token burn when no legal work exists.

## Core rule
A model turn is a bounded worker invocation, not a scheduler.
Do not try to force one turn to stay alive for five hours.
Use an external supervisor that relaunches bounded headless turns from durable state.

## State-aware supervisor behavior
1. Run one bounded read-only endgame turn.
2. If useful work was produced: persist checkpoint, recompute state fingerprint, relaunch quickly.
3. If the worker reports no real legal work: do not keep invoking the model. Enter token-free waiting outside the model and relaunch only when the fingerprint changes.
4. End after the configured wall-clock window.

## State fingerprint
At minimum include:
- local HEAD;
- relevant remote refs;
- tracked working-tree delta;
- ops/ai/GATE_STATE_CURRENT.md hash;
- newest relevant ops/ai/live or ops/ai/wall_results metadata.

A state change is a trigger, not proof.

## Worker behavior
Every overnight read-only worker must:
- read current gate first;
- prefer the earliest unfinished current gate;
- reuse unchanged evidence;
- avoid old PRE_CODEX/Ledger/runner-discovery/acceptance-harness work;
- never self-authorize source write;
- never self-authorize physical execution;
- create exact owner packets when the next step belongs to writer/dispatcher/physical owner;
- park when all useful legal work is owner-gated.

## Queue discipline
At least one Muse UI session reported a backlog-full limit of 4 messages.
Do not preload 30-100 messages into one UI.
Prefer one self-routing prompt plus external relaunch.

## Safety
- one source writer;
- one physical owner;
- no foreign PID/PGID/port takeover;
- no retry-to-pass;
- no secrets in logs/checkpoints;
- no Product Shell before positive pilot.
