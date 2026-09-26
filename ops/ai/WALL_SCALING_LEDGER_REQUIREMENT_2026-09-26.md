# Courier Wall Scaling + Ledger Requirement — 2026-09-26

Status: PRODUCT REQUIREMENT / DO NOT INSERT INTO CURRENT FINAL-CANDIDATE SOURCE SCOPE

## User-facing requirement

Courier must support an explicitly selectable logical wall size from **1 through 64**.

Examples:
- a user with one usable worker can select 1;
- starter/free-package UX should make 1 / 2 / 3 especially easy;
- a Windows or Mac host with capacity for 10 can request 10;
- a larger operator can request any exact integer up to 64.

The requested wall size is a capacity target, not permission to start 64 heavy processes.

## Required runtime semantics

Persist and display at least:

- requested_slots: integer 1..64
- admitted_slots: number currently permitted by resource/cost/provider guards
- active_slots: number currently executing useful work
- waiting_slots: authorized slots waiting for dependency-safe READY work
- guarded_slots: requested slots temporarily withheld by safety/resource/cost constraints
- reserved_interactive_slots: capacity intentionally held for live/coordinator work
- max_heavy_jobs: separate invariant; currently 1 unless a later proven policy explicitly changes it
- round_wall_clock_budget: bounded duration for an unattended work round
- stop_reason / throttle_reason when admitted_slots < requested_slots

Never silently claim all requested slots are active.

## Smooth-over-max rule

Prefer a stable smaller wall over a larger degraded one.

Example principle:

**smooth 10-slot wall > laggy 16-slot wall**

when 16 causes material latency, swap/pagefile growth, thermal/resource pressure, API waste or duplicated work.

Admission should be adaptive and truthful.

## Featherlight rule

A wall slot is a logical lease/capacity unit, not necessarily a resident AI process.

Prefer event/result-driven dispatch:
READY work -> claim/lease -> execute -> DurableResult -> verify -> reconcile -> release/reuse slot.

Idle slots should consume near-zero CPU/RAM/API work. No resident AI polling merely to keep a wall visually full.

## Ledger binding

The wall must ultimately be driven by the canonical Trusted Ledger, not by manual terminal-window count.

Every dispatched unit must bind to durable:
Goal -> Task -> Attempt -> Dispatch/Execution -> Result -> Evidence -> Verification -> Reconciliation.

One mutable scope still has at most one active writer. Read-only work may fan out when independent.

Requested slot count must not weaken idempotency, duplicate/replay rules, trusted-content rules, restart recovery, or exact candidate/runtime binding.

## Long unattended rounds

Long rounds are desired when useful, including **up to 10-hour sleep sessions**.

A long round must remain bounded by:
- wall-clock budget
- retry/failure ceilings
- provider/API budget
- host resource guard
- dependency-safe READY work
- repeated-state/no-progress detection
- context-hygiene checkpoints

Longer duration is not permission for busywork. If no authorized READY work remains, persist IDLE/DONE/BLOCKED and stop.

## Context rotation

Long-lived sessions must not accumulate obsolete context indefinitely.

Before clearing/rotating:
- checkpoint durable result/evidence;
- record exact next action;
- preserve writer/lease identity;
- then start a fresh minimal-context session.

See:
ops/ai/CONTEXT_HYGIENE_AND_HANDOFF_POLICY_2026-09-26.md

## Current implementation note

Existing scripts/run_autonomous_supervisor.py already models an 8-hour default session wall-clock budget but currently defaults max_active_tasks=1 and heavy_job_limit=1.

Canonical product plan still marks Trusted Ledger IN_PROGRESS and Zero-Human A->B / Restart & Recovery NOT_PROVEN. Therefore this 1..64 wall requirement is recorded now but must not derail the current final-candidate + physical-proof critical path.

## Near-term order

1. finish final canonical candidate and targeted tests
2. independent code-grounded review
3. physical RUN_1 A->verify->B zero relay
4. physical RUN_2 restart/no-A-replay
5. then bind scalable logical wall scheduling to the trusted ledger and expose exact 1..64 user control without weakening resource safety
