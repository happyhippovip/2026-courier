# Courier Overnight Autonomy Protocol — CURRENT

Status: DURABLE OPERATING RULE
Date: 2026-09-28

## Goal
Let Courier workers make useful progress for hours without requiring the founder to refill windows, while avoiding token burn when no legal work exists.

## Core rule
A model turn is a bounded worker invocation, not a scheduler.
Do not try to force one turn to stay alive for five hours.
Use an external supervisor that relaunches bounded headless turns from durable state.

## Muse headless contract
Use Muse Code headless mode with muse exec, --prompt-file, --max-model-steps, --workspace and --trust-workspace.

For unattended runs prefer --disable-approval with the sandbox retained.
Avoid --yolo for ordinary overnight work because it also disables the sandbox.

## State-aware supervisor behavior
1. Run one bounded read-only endgame turn.
2. If useful work was produced: persist checkpoint, recompute state fingerprint, relaunch quickly.
3. If worker emits NO_REAL_WORK: do not keep invoking the model. Enter token-free shell waiting, periodically fetch/read local state, and relaunch only when the fingerprint changes.
4. End after the configured wall-clock window.

## State fingerprint
At minimum include local HEAD, relevant remote refs, tracked working-tree delta, GATE_STATE_CURRENT.md hash, and newest relevant live/wall-results metadata.

A state change is a trigger, not proof.

## Worker behavior
Every overnight read-only worker must read current gate first, prefer the earliest unfinished current gate, reuse unchanged evidence, avoid old PRE_CODEX/Ledger/runner-discovery/acceptance-harness work, never self-authorize source write or physical execution, and emit NO_REAL_WORK only when all useful legal work is genuinely owner-gated.

## Queue discipline
Observed UI backlog limit: 4 messages in at least one Muse session.
Do not preload 30-100 messages into one UI.
Prefer one self-routing prompt plus external headless relaunch.

## Safety
One source writer. One physical owner. No foreign PID/PGID/port takeover. No retry-to-pass. No secrets in logs/checkpoints. No Product Shell before positive pilot.
