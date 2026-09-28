# Today Post-Ledger Model Staffellauf — 2026-09-28

Current durable gate at creation:
PRE_CODEX_STATE=DURABILITY_PENDING
AUTHORITATIVE_READY=NO

## Now — Windows + Mac parallel
Windows Google:
- 1x WINDOWS_HNI_01 gate durability owner
- 7-12x WINDOWS_HNI_02..20 independent prep
Mac Google:
- 12-20x MAC_AFTER_LEDGER / MAC_HNI finish tasks
Heavy jobs: max 1 per host

## Opus 4.6 — now, not wall-scale
Use 3-4 windows:
1 POST_LEDGER_CRITICAL_PATH
2 POST_LEDGER_RUN_PROOF
3 POST_LEDGER_CORE_FREEZE
4 MOTOR_RELIABILITY_JUDGE optional

Expected result:
a small number of high-value convergence decisions, not implementation.

## Claude/Sonnet — after current Google packets are durable
Use 3-4 windows if genuinely available:
- Proof semantics
- Continuity
- Cost/routing
- Pilot semantics prep
Do not use Sonnet for work Google already proves deterministically.

## "3.1" / "Supercode"
No canonical provider/model entry currently exists in the Courier registry.
Use UNKNOWN_MODEL_CONSERVATIVE_SELF_ID_CANARY first.
One window each maximum until actual identity/capability is proven.
No source-write authority from name alone.

## Codex
Do not run now while PRE_CODEX is DURABILITY_PENDING.
When AUTHORITATIVE_READY=YES:
1x PRE_CODEX handoff assembler
then exactly 1x CODEX_HIGH_ONCE_FIXED_CANDIDATE_REVIEW.

## After Codex green
Mac:
exact binding -> 1 physical RUN_1 owner.
After RUN_1 PASS -> 1 physical RUN_2 owner.
After RUN_2 PASS -> Core Freeze.
Then minimum real pilot.
Product Shell only after positive pilot signal.

## When should visible results appear?
First useful result is not a clock-time promise.
The next externally meaningful checkpoints are:
1 authoritative FINAL_SHA/gate becomes READY;
2 Codex returns READY_FOR_PHYSICAL_RUN=YES;
3 RUN_1 PASS with zero-human A->B;
4 RUN_2 PASS with no A replay;
5 Core Freeze;
6 real pilot signal.
