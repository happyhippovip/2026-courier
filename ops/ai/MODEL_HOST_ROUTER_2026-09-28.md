# Courier Model / Host Router — 2026-09-28

Status: CANONICAL ROUTING POLICY
Purpose: choose the cheapest capable model/host/window for each READY task and tell the operator exactly where to run it.

## Routing principles

1. DETERMINISTIC FIRST
   - shell / git / Python / pytest / hashes / JSON checks before model reasoning.
2. CHEAPEST CAPABLE MODEL
   - use Google CLI for routine queue execution, deterministic review, harvesting, bounded tests.
   - use Muse for independent QA, contradiction hunting, proof/restart/core-freeze review.
   - use Opus 4.6 only for high-value convergence/semantic judgment, not repetitive queue work.
   - use Codex HIGH exactly once when PRE_CODEX gate is durably READY for the exact fingerprint.
3. HOST FIT
   - Windows: Ledger/server/integration, targeted tests, candidate-sensitive deterministic evidence, gate persistence owner.
   - Mac: physical-proof preparation, restart/no-replay prep, runtime binding, Proof Cards/Core Freeze, Muse QA.
4. COST-SAFE GATES
   - same gate fingerprint gets at most one validation owner.
   - DURABILITY_PENDING gets at most one persistence owner.
   - other workers skip the gate family.
5. MAX_HEAVY_JOBS=1 per host.
6. MANY WINDOWS != MANY HEAVY JOBS.
7. If no genuine READY work exists, recommend TRUE_IDLE rather than filler.

## Provider roles

### GOOGLE_CLI
Best for:
- queue execution
- harvesting
- exact reads
- deterministic checks
- targeted pytest
- Ledger/replay/trusted-content/reconcile work
- cost/resource/continuity checks
- routine synthesis

Default multiplicity:
- Windows: 4-20 logical windows, depending on READY count
- Mac: 4-12 logical windows, depending on READY count
- never exceed real unclaimed READY work

### MUSE
Best for:
- independent QA
- contradiction/stale-evidence audit
- restart-matrix review
- RUN_1/RUN_2 proof-prep review
- Proof Card/Core Freeze QA
- wall reliability/cost/continuity QA

Default multiplicity:
- 2-8 windows
- use only on distinct claims/families

### OPUS_4_6
Best for:
- semantic convergence
- architecture/invariant consistency
- autonomy/human-relay semantics
- final proof design review
- pilot convergence

Default multiplicity:
- 1-4 windows
- upper practical bound 6
- never 100x

### CODEX_HIGH
Best for:
- exact final code-grounded review
- only after durably READY PRE_CODEX fingerprint

Multiplicity:
- exactly 1
- repeat only if FINAL_SHA/evidence fingerprint changes and invalidates review

### ANTIGRAVITY_WINDOWS
Best for:
- sole final-candidate application source writer
Multiplicity:
- exactly 1 writer for mutable final scope

### ANTIGRAVITY_MAC
Best for:
- physical RUN_1 / RUN_2 owner after authorization
Multiplicity:
- exactly 1 physical runner per run

## Required router output

Every routing pass must output:

ROUTING_STATE=
CURRENT_PHASE=
GATE_STATE=
TOP_BLOCKER=

WINDOW_PLAN:
- HOST=
- PROVIDER=
- ROLE=
- PROMPT_PATH=
- COUNT=
- HEAVY_JOB_COUNT=
- WHY=
- START_CONDITION=
- STOP_CONDITION=

DO_NOT_START:
- provider/host/family combinations that would duplicate work or cost

NEXT_HUMAN_ACTION=
ESTIMATED_DUPLICATION_RISK=LOW|MEDIUM|HIGH

## Auto-admission rules

Before recommending a new window:
- inspect durable claims/results;
- count real READY unclaimed tasks by family;
- subtract live claims;
- reuse existing result fingerprints;
- respect gate locks and physical-run ownership;
- do not recommend a model family already saturated by live claims.

## Transition examples

If PRE_CODEX_STATE=DURABILITY_PENDING:
- 1 Windows gate-persistence owner
- 0 duplicate PRE_CODEX validators
- Google/Muse may work unrelated prep
- Codex=0

If PRE_CODEX_STATE=READY:
- Codex HIGH=1
- stop PRE_CODEX validation family
- Mac may continue legal prep
- Windows may continue unrelated durable work

If READY_FOR_PHYSICAL_RUN=YES:
- Mac Antigravity physical RUN_1=1
- no duplicate physical runners
- support workers may observe/read only

If RUN_1=PASS:
- RUN_2 prep/runner family unlocks

If RUN_2=PASS:
- Core Freeze / Proof closure gets priority

If all relevant queues exhausted:
- TRUE_IDLE
- do not recommend more windows merely because capacity exists
