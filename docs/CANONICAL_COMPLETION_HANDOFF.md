# Canonical Completion & Handoff Protocol

Status: REQUIRED for all future Courier phases and major runs.

Purpose: every run must leave a durable, machine-readable checkpoint so that any next agent can resume from the last proven state after account switches, model limits, crashes, stalled processes, restarts, or operator handoffs.

## Core rule

A run is not terminal merely because an agent says it is done. Terminal state is evidence-backed and expressed through canonical YES/NO completion flags plus fingerprints, exact test counts, verified IDs, blocker state, and active-work state.

The next agent MUST read the latest canonical handoff record before doing any work. It MUST reuse proven unchanged state and MUST NOT restart completed work unless the repository or canonical state is missing or invalid.

## Required terminal flags

Every major run must publish at least:

- `GOAL_SATISFIED: YES|NO`
- `REGRESSION_PASS: YES|NO`
- `PRODUCT_TESTS_PASS: YES|NO`
- `COURIER_TESTS_PASS: YES|NO`
- `SINGLE_WRITER_PRESERVED: YES|NO`
- `HUMAN_GATE_REQUIRED: YES|NO`
- `ACTIVE_WORK_AT_END: NONE|<description>`
- `UNRESOLVED_BLOCKER: NONE|<description>`
- `MANUAL_STATE_SURGERY_USED: YES|NO`
- `DIRECT_BYPASS_USED: YES|NO`
- `READY_FOR_NEXT_GOAL: YES|NO`

Recommended additional evidence:

- `ENDING_FINGERPRINT`
- `PRODUCT_TEST_COUNT`
- `COURIER_TEST_COUNT`
- `VERIFIED_GOAL_ID`
- `LAST_VERIFIED_MISSION_ID`
- `LAST_VERIFIED_TASK_HASH`
- `TIMESTAMP_UTC`
- `CURRENT_GOAL`
- `NEXT_SAFE_ACTION`

## Readiness derivation

`READY_FOR_NEXT_GOAL` may be `YES` only when all required conditions are proven:

- `GOAL_SATISFIED = YES`
- required regressions pass
- product tests pass when applicable
- Courier tests pass when applicable
- `SINGLE_WRITER_PRESERVED = YES`
- `HUMAN_GATE_REQUIRED = NO`
- `ACTIVE_WORK_AT_END = NONE`
- `UNRESOLVED_BLOCKER = NONE`
- `MANUAL_STATE_SURGERY_USED = NO`
- `DIRECT_BYPASS_USED = NO`

If any required condition is not met, `READY_FOR_NEXT_GOAL` MUST be `NO`.

## Resume behavior

On every new agent/session/account/model/folder handoff:

1. Read the newest canonical handoff record.
2. Verify the referenced repository/fingerprint still matches or classify the delta.
3. Reuse completed verified work when unchanged.
4. If `READY_FOR_NEXT_GOAL = YES`, continue from that checkpoint without repeating completed work.
5. If `READY_FOR_NEXT_GOAL = NO`, identify the first blocking `NO` or unresolved blocker and continue only from that point.
6. Never silently rewrite canonical goal/mission state to manufacture progress.
7. Never bypass Courier by manually invoking a worker to fake continuation.
8. After recovery or completion, write a new canonical handoff record.

## Failure/restart rule

A process crash, quota reset, account switch, timeout, UI restart, or stalled task is an execution interruption, not evidence that work should restart from zero. Repository state + canonical handoff + verified fingerprints/tests determine the restart point.

## Evidence rule

Flags are claims only when backed by evidence. The terminal record should reference exact test counts, fingerprints, verified IDs, and blocker details. Narrative summaries never override failed evidence.

## Safety invariants

The handoff protocol does not relax safety constraints. Preserve at minimum:

- `TRUTH > SPEED`
- `SINGLE_WRITER = YES`
- `HEAVY_JOB_LIMIT = 1`
- human-only gates remain human-only
- no spend, purchases, overages, deployment, external sends, real-money trading, wallet signing, or account-rotation automation without explicit authorization

## Phase rule

This protocol is permanent infrastructure. All future Courier finishing phases, autonomy tests, product milestones, Codex audits, repair cycles, and final acceptance runs must end with a canonical handoff record conforming to `schemas/canonical_handoff.schema.json`.
