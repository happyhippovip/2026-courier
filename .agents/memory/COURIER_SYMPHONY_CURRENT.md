# Courier Symphony — Current Project Memory

Updated: 2026-09-28
Status: CURRENT COORDINATION MEMORY

## Product
Courier Symphony is the orchestration + proof system whose desired behavior is:
"Du bist im Urlaub. Courier arbeitet weiter."

## Critical path
Exact durable candidate -> smallest required writer pass -> changed-byte review -> exact Mac binding -> physical RUN_1 -> physical RUN_2 -> Core Freeze -> minimum real pilot -> Product Shell only after positive pilot.

## Durable runner
Recovered runner branch: runner-recovery/e9b4f15f-20260928
Recovered runner SHA: e9b4f15f8bc45be3d2bc2d9ab4f3c8ead7a77939
Base candidate: 34b0a4264bf763bc2a78f761ffba36e47706b2cf
The recovered branch was verified as 12 commits ahead / 0 behind the base.

## Late candidate conflict
Latest local evidence reported a fixed-but-orphaned commit prefix dfd22bb with no durable remote branch/worktree at observation time.
Do not treat the prefix as a RUN_ID.
Current physical proof is blocked until one exact candidate is adopted and FINAL_SHA == REMOTE_SHA == LOCAL_SHA == BOUND_SHA.

## Blocker families to keep closed on final bytes
verifier/key custody; N1 stale execute_run1; N2 RUN1->RUN2 false-green; transition/result provenance; synthesized DONE->SUCCESS; truthful exit status; human-relay proof; RUN2 desimulation; expected-hash authority; artifact/result identity.

## Proof status boundary
Source-grounded mechanism evidence exists for Result -> Verify -> Reconcile -> NEXT_READY, B automatic continuation/exactly-once mechanics, restart/no-replay fail-closed behavior, and bounded process/resource admission.
These are mechanism proofs, not accepted physical RUN_1/RUN_2 certification.

## Multi-agent rules
Exactly one writer. Exactly one physical owner. Read-only walls only do unique lanes. If the early gate is exclusive-owner blocked, other windows park. No filler.

## Overnight lesson
A model turn is not a scheduler.
Use bounded headless invocations plus an external state-aware supervisor.
NO_REAL_WORK means checkpoint owner/trigger and wait outside the model with zero model tokens until state changes.
Muse UI queue stuffing is not reliable; an observed session reported a backlog-full limit of 4.

## Founder-relay rule
The founder should not be the copy/paste bus. Prefer durable checkpoints, routing, external supervisors, and exact next-owner triggers.

## Scope
Ledger frozen absent explicit retest.
Product Shell locked until positive real pilot.
