# COURIER PROGRESS BEACON CONTRACT

**Canonical date:** 2026-09-10
**Status:** DEFERRED IMPLEMENTATION / REQUIRED POST-KERNEL-FREEZE VISIBILITY

## Purpose

Give the founder a compact, trustworthy view of whether Courier is progressing, stalled, blocked, overheating a machine, repeating work, or losing model cost — without requiring screenshots, log tailing, or manual process inspection.

This is a visibility contract, NOT a second scheduler, planner, verifier, or source of truth.

## Core rule

The beacon MUST be derived from canonical durable Courier state and evidence. It may summarize state, but it MUST NOT mutate task/goal/verification truth or declare PASS by itself.

No dashboard work may interrupt the current Copy-Paste Exit critical path. Implementation is deferred until the kernel freeze gate or until lack of visibility becomes a reproducible blocker.

## Founder status line

Every active goal should expose one compact line conceptually equivalent to:

`COURIER 75% | PHASE Auto-Continue | STATE PROGRESSING | ETA/AGE evidence-based | MAC NORMAL | WIN NORMAL | HUMAN RELAYS 0 | PROOF DEBT 1 | COST €x | NEXT Coding E2E`

Percent is an estimate derived from explicit phase gates, not model confidence or worker prose.

## Required fields

- goal_id / active task_id / attempt_id
- overall_progress_percent (0-100)
- current_phase
- phase_progress_percent
- state: `QUEUED | RUNNING | PROGRESSING | WAITING_VALID | STALLED | BLOCKED | HUMAN_GATE | EXECUTION_UNCERTAIN | VERIFIED_COMPLETE`
- last_real_progress_at
- last_progress_evidence_ref
- current_worker / machine
- active_process_count and owned_heavy_process_count
- machine resource state per host
- thermal state where supported
- human_relays_for_goal
- proof_debt_count
- unresolved_current_blockers
- follow_up_count
- model/tool cost if available
- retry/repair count
- next_safe_action
- expected_completion_condition

## Percent model

Do not compute progress from elapsed time, tokens, number of commands, or worker claims.

Progress comes from weighted verified phase gates. For the current Courier kernel, canonical gates are:

1. real programmatic worker proof — 15%
2. auto-continue proof with zero human relay — 20%
3. real isolated coding E2E — 20%
4. durable Human-Gate pause/resume — 15%
5. controlled restart/recovery without duplicate execution — 15%
6. adversarial false-positive/P0 check — 10%
7. freeze decision + canonical evidence package — 5%

A gate contributes only when independently evidenced. Partial implementation without proof may be displayed as `IMPLEMENTED_UNVERIFIED` but does not earn the full verified weight.

If a previously accepted gate is invalidated by stronger evidence, the percentage may decrease, but the beacon must state exactly why. Cosmetic architecture changes must never reset valid completed gates.

## Slow / wrong-direction detection

The beacon should flag, but not automatically kill work, when any of the following occur:

- no new progress evidence after the configured soft-check interval
- repeated execution of the same proof/test/action without new information
- rising proof debt while build work continues
- repeated repair of the same root cause
- active heavy process without owner/lease
- orphaned monitoring/debug helper
- machine enters PRESSURE or THERMAL_PRESSURE
- human relay count increases
- full-suite/broad regression is repeatedly invoked during targeted debugging
- cost/tokens/tool calls rise without a verified phase transition
- current task diverges from the Outcome Contract

Recommended founder-facing flags:
`OK | SLOW_CHECK | LOOP_RISK | PROOF_DEBT | RESOURCE_PRESSURE | BLOCKED | HUMAN_GATE | EXECUTION_UNCERTAIN`.

## Anti-false-alarm policy

Time alone never means failure or hang. A long test with real progress evidence is `PROGRESSING`.
A short loop with repeated commands and no new evidence may be `LOOP_RISK` even if CPU is busy.

## Notification policy

Do not spam the founder with heartbeats.
Surface only:
- meaningful verified phase completion
- LOOP_RISK / STALLED after evidence-based checks
- BLOCKED / EXECUTION_UNCERTAIN
- HUMAN_GATE
- thermal/resource pressure requiring attention
- VERIFIED_COMPLETE / FREEZE_CANDIDATE

Normal heartbeats stay in the ledger.

## Permanent anti-regression requirement

Any future Courier UI/dashboard/CLI status command must read this contract and remain read-only over canonical task/outcome truth.

The simplest acceptable first implementation is a terminal/status JSON or one-line CLI summary. A web dashboard is optional and must never be required for Courier operation.
