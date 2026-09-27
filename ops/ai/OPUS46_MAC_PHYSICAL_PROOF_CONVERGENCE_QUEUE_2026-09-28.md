# Opus 4.6 Mac Physical-Proof Convergence Queue — 2026-09-28

Status: C4 / READ_ONLY / PREP-AND-JUDGMENT ONLY
Host: MAC preferred
Purpose: high-value semantic review of RUN_1/RUN_2/Core-Freeze readiness without executing physical runs.

## Hard laws
- no physical RUN_1/RUN_2 execution
- no application-source edits
- RESULT_REUSE_FIRST
- no PRE_CODEX revalidation
- no deterministic Google/Muse duplication
- one live claim per task
- UNKNOWN stays UNKNOWN

## Tasks

### MOP-01 — Exact runtime-binding semantics
What exact source/build/runtime/config evidence must prove the Mac is running the intended candidate?

### MOP-02 — RUN_1 falsifiability
Can the RUN_1 plan actually disprove A-once, verify/reconcile, B-auto-start, zero-relay, no-failed-execution claims?

### MOP-03 — RUN_1 minimal evidence set
Reduce RUN_1 capture to the smallest decisive evidence packet.

### MOP-04 — RUN_2 restart/no-replay semantics
Define exact evidence needed to prove A is not re-executed after restart while B continues automatically.

### MOP-05 — Failed-execution contamination
Define how any FAILED execution must invalidate or quarantine a physical proof.

### MOP-06 — Human-relay accounting
Pressure-test HUMAN_RELAY_COUNT and distinguish setup, authorization, recovery and runtime relay.

### MOP-07 — Isolation/ownership semantics
Review process/port/state/artifact/log ownership required so the physical proof is attributable and noninterfering.

### MOP-08 — Restart timing ambiguity
Identify race windows around persist/verify/reconcile/dispatch where logs could falsely imply correctness.

### MOP-09 — Proof Card binding
Review Source/Build/Runtime/Covered Surface/UNKNOWN/Human Intervention bindings for RUN evidence.

### MOP-10 — Core Freeze decision
Define exact boundary from RUN_1/RUN_2 results to CORE_FREEZE, including revalidation triggers.

### MOP-11 — Pilot unlock semantics
Define the minimum honest proof result that permits the minimal pilot lane to start.

### MOP-12 — Final Mac physical-proof synthesis
Inputs MOP-01..11 only.
Output:
RUNTIME_BINDING_READY=
RUN1_PLAN_READY=
RUN2_PLAN_READY=
HUMAN_RELAY_SEMANTICS_READY=
ISOLATION_READY=
PROOF_CARD_READY=
CORE_FREEZE_READY=
PILOT_UNLOCK_READY=
TOP_RISK=
NEXT_EXACT_ACTION=

Do not create MOP-13 without a new invalidation trigger/operator authorization.
