# Courier 4-Week / 160-Hour Durable Work Plan — 2026-09-28

Purpose: provide four full 40-hour weeks of real forward work so workers do not need new chat instructions every few minutes.

Global rules:
- 4 weeks x 40 hours = 160 nominal operator/worker hours.
- Every day is 8 hours split into four 2-hour work blocks.
- A block may complete early; immediately claim the next unlocked block.
- RESULT_REUSE_FIRST=YES
- CLAIM_BEFORE_ANALYSIS=YES
- FAMILY_COMPLETE != GLOBAL_TRUE_IDLE
- temporary empty queue -> harvest -> replenish -> backoff -> refresh -> continue
- MAX_HEAVY_JOBS=1 per host
- no duplicate PRE_CODEX validators
- Codex HIGH exactly once per unchanged authoritative fingerprint
- RUN_1/RUN_2 exactly one physical owner each
- no Product Shell before durable positive real-pilot signal
- no filler work to consume hours

## Week 1 — Reliability + Motor + Ledger closure
Goal: Stop false-idle, stop failing scheduled motor runs, close Ledger semantics, make PRE_CODEX durability real.

### Day 1: Motor reliability
Verify fixed Courier Motor scheduled run, inspect verifier authority, state persistence, concurrency, failure mail behavior, and add regression coverage.

### Day 2: Ledger closure
Harvest GLEDGER/Google/Muse/Opus results, close exact remaining Ledger blockers, finish identity/persistence/replay/reconcile semantics.

### Day 3: Gate durability
Single-owner FINAL_SHA durability bridge, candidate handoff integrity, 12-case evidence packet, stale-evidence invalidation.

### Day 4: Autonomy reliability
Persistent idle/backoff, queue replenishment, claim/lease, result cache, provider isolation, crash/restart continuity.

### Day 5: Week-1 convergence
Synthesize only unresolved P0/P1 issues, prepare exact PRE_CODEX packet, stop all completed families.

## Week 2 — Codex gate + Mac physical proof
Goal: Consume PRE_CODEX once, bind exact Mac runtime, execute RUN_1 then RUN_2 with zero-human continuation proof.

### Day 1: PRE_CODEX/Codex
If authoritative gate READY: assemble compact packet and invoke exactly one Codex HIGH. If not READY: only durability owner works blocker; all others do Mac candidate-independent prep.

### Day 2: Mac exact binding
Source/build/runtime/config fingerprint binding, process/port/state/log/artifact isolation, command sheets, proof capture layout.

### Day 3: RUN_1
One physical runner only. Prove A once, trusted expected hash, server bytes, verify/reconcile, B auto-start, relay=0, no FAILED execution.

### Day 4: RUN_2
One controlled restart proof. Persist A, restart, no A replay, reconcile resumes, B auto-start, A execution count remains 1.

### Day 5: Physical proof convergence
Assemble Proof Cards, failure matrix, retest triggers, exact remaining blockers; no architecture reopening.

## Week 3 — Core Freeze + minimum real pilot
Goal: Freeze the proven core, then run the smallest honest user pilot with measurable value and support cost.

### Day 1: Core Freeze
Trusted Ledger, Reliable Motor, NEXT_READY, zero-human continuation, restart, resource bounds, Proof Cards, fingerprints, no gate-violating UNKNOWN.

### Day 2: Pilot readiness
Goal Contract, permission/privacy boundaries, onboarding, setup-time measurement, issue classification, success/failure evidence.

### Day 3: Pilot execution
Run minimum real pilot only if Core Freeze is durable. Capture setup time, intervention points, completed work, failure evidence, support effort.

### Day 4: Pilot evidence review
Independent Muse/Opus review of pilot evidence, false-positive value signals, privacy, support burden, repeatability.

### Day 5: Pilot decision packet
Produce positive/negative/unknown signal packet. Unlock Product Shell only on durable positive signal; otherwise plan smallest corrective iteration.

## Week 4 — Product Shell + release readiness
Goal: Turn proven pilot needs into the smallest sellable shell, release controls, update/rollback fabric, and operator handoff.

### Day 1: Product Shell scope
Only pilot-proven user needs: Arbeit/Braucht dich/Fertig/Proof/Next, minimal onboarding, safe settings, support/observability.

### Day 2: Implementation packets
Generate bounded writer packets with one owner per file/scope, acceptance tests, no speculative marketplace/enterprise work.

### Day 3: Release reliability
Install/update/rollback/LKG, delta/dedupe, failure recovery, upgrade compatibility, crypto-agility inventory.

### Day 4: User/owner surfaces
Honest status projection, reported vs verified, waiting/blocker reason, next legal action, safe stop/retry visibility.

### Day 5: Ship packet
Release checklist, evidence index, known limitations, pilot feedback loop, support playbook, next-30-day backlog.

## Operator cadence

Use one phase router/replenisher continuously.
Workers should consume current week/day blocks from durable queue files.
If a future week is still gated, use only candidate-independent prep from that week; do not violate phase gates.
At the end of each day, write one compact checkpoint: DONE, OPEN, BLOCKED, NEXT.
At the end of each week, write one convergence packet and stop completed review families.

## Success condition

The plan is not complete because 160 hours elapsed.
It is complete when the critical path reaches the strongest evidence-backed state possible:
PRE_CODEX -> Codex -> RUN_1 -> RUN_2 -> Core Freeze -> Pilot -> Product Shell/Release only when gates permit.
