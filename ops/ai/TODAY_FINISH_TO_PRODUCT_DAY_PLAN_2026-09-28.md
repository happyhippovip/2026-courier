# Courier Today — Finish to Product Day Plan — 2026-09-28

Status: OPERATOR EXECUTION PLAN
Current hard blocker at plan creation:
PRE_CODEX_STATE=DURABILITY_PENDING
REPORTED_FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
AUTHORITATIVE_READY=NO
Reason: FINAL_SHA not durably resolvable from canonical remote.

Global laws:
- RESULT_REUSE_FIRST=YES
- NO_DUPLICATE_REVIEW=YES
- FAMILY_COMPLETE != GLOBAL_TRUE_IDLE
- MAX_HEAVY_JOBS=1 per host
- one gate persistence owner only
- Codex HIGH exactly once after authoritative PRE_CODEX READY
- physical RUN_1 only after READY_FOR_PHYSICAL_RUN=YES
- RUN_2 only after RUN_1 PASS
- Product Shell only after positive pilot signal

## MORNING — close Ledger + make gate durable

WINDOWS GOOGLE:
- 6x ops/ai/TODAY_GOOGLE_LEDGER_CLOSE_WORKER_PROMPT.txt
- 1x ops/ai/GOOGLE_GATE_DURABILITY_BRIDGE_SINGLE_OWNER_PROMPT.txt
- 2x ops/ai/GOOGLE_WINDOWS_BLOCKER_PACKET_100X_PROMPT.txt
- 2x ops/ai/GOOGLE_WINDOWS_WRITER_PACKET_VALIDATOR_100X_PROMPT.txt
Recommended total: 11 logical windows.

MUSE:
- 6x ops/ai/MUSE_LEDGER_ADVERSARIAL_FINISH_WORKER_PROMPT.txt
- 4x ops/ai/MUSE_FALSE_GREEN_FALSIFICATION_100X_PROMPT.txt
- 4x ops/ai/MUSE_RESTART_MATRIX_REVIEW_100X_PROMPT.txt
Recommended: 14 windows initially. Scale only with distinct claims.

OPUS 4.6:
- 2x ops/ai/OPUS46_LEDGER_FINAL_CONVERGENCE_WORKER_PROMPT.txt
- 1x ops/ai/OPUS46_LEDGER_BLOCKER_ARBITER_PROMPT.txt
Recommended: 3 windows.

MORNING EXIT:
- GLEDGER-130 complete or exact blocker list known
- OL-13 complete
- ML-12 complete
- Ledger gate-violating UNKNOWNs closed/explicitly blocked
- exactly one gate persistence owner resolves/persists candidate if possible

## MIDDAY — PRE_CODEX -> CODEX ONCE

Only if authoritative PRE_CODEX becomes READY:
GOOGLE WINDOWS:
- 1x ops/ai/TODAY_PRE_CODEX_HANDOFF_ASSEMBLER_PROMPT.txt
- 2x ops/ai/GOOGLE_RESULT_CACHE_INTEGRITY_100X_PROMPT.txt
- 2x ops/ai/GOOGLE_PROOF_PACKET_ASSEMBLER_100X_PROMPT.txt

OPUS:
- 1x ops/ai/OPUS46_FINISH_CRITICAL_PATH_JUDGE_PROMPT.txt

CODEX:
- EXACTLY 1x HIGH on exact durable FINAL_SHA/fingerprint
- no second Codex unless fingerprint changes and invalidates review

If PRE_CODEX remains DURABILITY_PENDING:
- do not start Codex
- continue Mac non-candidate prep, Ledger closure, proof prep, continuity
- do not create duplicate gate validators

## AFTERNOON — Mac binding + RUN_1 / RUN_2 path

MAC GOOGLE before physical authorization:
- 3x ops/ai/TODAY_MAC_POST_CODEX_PROOF_PREP_PROMPT.txt
- 2x ops/ai/GOOGLE_MAC_RUNTIME_BINDING_100X_PROMPT.txt
- 2x ops/ai/GOOGLE_MAC_ARTIFACT_PROOF_CHAIN_100X_PROMPT.txt
- 2x ops/ai/GOOGLE_MAC_PROCESS_RESOURCE_GUARD_100X_PROMPT.txt
- 2x ops/ai/GOOGLE_MAC_RESTART_NEGATIVE_CASES_100X_PROMPT.txt
- 2x ops/ai/GOOGLE_MAC_PROOF_CARD_ASSEMBLER_100X_PROMPT.txt
Recommended: 13 logical Mac Google windows.

MUSE:
- 4x ops/ai/TODAY_MUSE_RUN_PROOF_QA_PROMPT.txt
- 2x ops/ai/MUSE_CROSS_PROVIDER_CONTINUITY_QA_100X_PROMPT.txt

OPUS 4.6 MAC:
- 2x ops/ai/OPUS46_MAC_TODAY_REUSABLE_WORKER_PROMPT.txt
- 1x ops/ai/OPUS46_RUN_PROOF_MINIMALITY_JUDGE_PROMPT.txt
Recommended: 3 windows.

PHYSICAL OWNER:
- 1x Mac Antigravity only after READY_FOR_PHYSICAL_RUN=YES.
RUN_1 must prove A once -> Result A -> trusted expected hash -> server bytes -> verify/reconcile -> B auto-start -> HUMAN_RELAY_COUNT=0 -> no FAILED execution.

After RUN_1 PASS:
- switch support workers to RUN_2/restart/no-replay
- 1 physical Mac runner for RUN_2
- prove persisted A survives restart, A not re-executed, reconcile resumes, B starts automatically, A count stays 1.

## EVENING — Core Freeze -> Pilot

After RUN_2 PASS:
GOOGLE:
- 4x ops/ai/TODAY_CORE_FREEZE_CLOSURE_WORKER_PROMPT.txt
- 2x ops/ai/GOOGLE_MAC_PROOF_CARD_ASSEMBLER_100X_PROMPT.txt
- 2x ops/ai/GOOGLE_MAC_OBSERVABILITY_EVIDENCE_100X_PROMPT.txt

MUSE:
- 4x ops/ai/TODAY_MUSE_CORE_FREEZE_QA_PROMPT.txt

OPUS:
- 1x ops/ai/OPUS46_CORE_FREEZE_READY_JUDGE_PROMPT.txt
- 1x ops/ai/OPUS46_FINISH_CRITICAL_PATH_JUDGE_PROMPT.txt

CORE FREEZE requires:
Trusted Ledger
Reliable Motor
Result->Verify->Reconcile->NEXT_READY
zero-human A->B
restart proof
Autonomy Grade / Covered Surface
bounded resources/no tight polling
Proof Cards
fingerprints
no gate-violating UNKNOWNs

After Core Freeze:
- 3x ops/ai/TODAY_MINIMUM_PILOT_PREP_WORKER_PROMPT.txt
- 2x ops/ai/MUSE_PILOT_EVIDENCE_QA_100X_PROMPT.txt if available
- 1x ops/ai/TODAY_OPUS_PILOT_UNLOCK_JUDGE_PROMPT.txt

No Product Shell until a positive real pilot signal exists.

## LATE EVENING / NEXT STEP

If positive pilot signal exists:
- 3x ops/ai/TODAY_PRODUCT_SHELL_BACKLOG_PREPARER_PROMPT.txt
- 1x Opus product-scope review
- Google handles deterministic implementation packets
- source writer remains explicitly authorized owner

If pilot signal is not positive or not yet real:
- do not build Product Shell
- close evidence gaps / prepare next pilot iteration
