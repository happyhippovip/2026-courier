# Muse 30-Window + Opus Mac Two-Round Plan — 2026-09-28

Purpose:
Exact window allocation for a 30-window Muse wall, followed by a bounded Opus 4.6 MacBook block, then a second review round.

Global:
- RESULT_REUSE_FIRST=YES
- one live claim per task
- no unchanged PRE_CODEX revalidation
- no application-source edits
- no physical RUN_1/RUN_2 unless separately authorized
- FAMILY_COMPLETE != GLOBAL_TRUE_IDLE
- MAX_HEAVY_JOBS=1 per host

## MUSE ROUND 1 — 30 windows

Windows 01-06:
ops/ai/MUSE_LEDGER_ADVERSARIAL_FINISH_WORKER_PROMPT.txt
Count: 6
Purpose: Ledger finish falsification / ML queue.

Windows 07-10:
ops/ai/MUSE_FALSE_GREEN_FALSIFICATION_100X_PROMPT.txt
Count: 4
Purpose: false-green review across current proof evidence.

Windows 11-14:
ops/ai/MUSE_CROSS_PROVIDER_CONTINUITY_QA_100X_PROMPT.txt
Count: 4
Purpose: session/provider/host continuity.

Windows 15-18:
ops/ai/MUSE_RESTART_MATRIX_REVIEW_100X_PROMPT.txt
Count: 4
Purpose: restart/no-replay evidence review.

Windows 19-22:
ops/ai/MUSE_SHARED_CAPABILITY_PRIVACY_QA_100X_PROMPT.txt
Count: 4
Purpose: shared-capability privacy / receive-vs-contribute review.
Lower priority than Ledger/proof families; if current critical-path QA remains, these windows should take MUSE_LATER_REUSABLE_REVIEW_WORKER_PROMPT.txt instead.

Windows 23-26:
ops/ai/MUSE_GOOGLE_CARRYOVER_100X_WORKER_PROMPT.txt
Count: 4
Purpose: distinct carryover QA families and compact reviews.

Windows 27-29:
ops/ai/MUSE_LATER_REUSABLE_REVIEW_WORKER_PROMPT.txt
Count: 3
Purpose: route among remaining distinct Muse-compatible QA families without repeating completed work.

Window 30:
ops/ai/MUSE_LATER_REUSABLE_REVIEW_WORKER_PROMPT.txt
Count: 1
Role: coordinator-style spare/router window.
This window should prefer unclaimed high-priority C2 QA and remain light.

Expansion rule:
Do not keep all 30 model-heavy if tasks are exhausted.
Completed family -> route to next family.
If fewer unique claims exist, idle/reuse rather than duplicate.

## OPUS 4.6 MACBOOK — AFTER MUSE ROUND 1 IS HARVESTED

Recommended: 6 windows.

Opus Mac 01-02:
ops/ai/OPUS46_MAC_TODAY_REUSABLE_WORKER_PROMPT.txt
Count: 2
Purpose: MOP physical-proof convergence.

Opus Mac 03:
ops/ai/OPUS46_RUN_PROOF_MINIMALITY_JUDGE_PROMPT.txt
Count: 1

Opus Mac 04:
ops/ai/OPUS46_CORE_FREEZE_READY_JUDGE_PROMPT.txt
Count: 1

Opus Mac 05:
ops/ai/OPUS46_LEDGER_BLOCKER_ARBITER_PROMPT.txt
Count: 1

Opus Mac 06:
ops/ai/OPUS46_FINISH_CRITICAL_PATH_JUDGE_PROMPT.txt
Count: 1

Do not use more than 6 simultaneously unless distinct unclaimed C4 tasks exist.
Do not spend Opus on deterministic Google/Muse tasks.

## ROUND 2 — AFTER FIRST-ROUND RESULTS ARE HARVESTED

Muse Round 2 recommended: 12-18 windows, not automatically all 30.

4x MUSE_LATER_REUSABLE_REVIEW_WORKER_PROMPT.txt
4x MUSE_FALSE_GREEN_FALSIFICATION_100X_PROMPT.txt only on newly changed evidence
4x MUSE_CROSS_PROVIDER_CONTINUITY_QA_100X_PROMPT.txt only where new first-round/Opus results changed continuity conclusions
2x MUSE_RESTART_MATRIX_REVIEW_100X_PROMPT.txt only for newly exposed restart gaps
2x MUSE_LEDGER_ADVERSARIAL_FINISH_WORKER_PROMPT.txt only if ML-12 / Ledger finish remains open
2x MUSE_SHARED_CAPABILITY_PRIVACY_QA_100X_PROMPT.txt only if critical-path families are already closed

Opus Round 2 recommended: 4 windows.

2x OPUS46_1H_ELITE_DECISION_WORKER_PROMPT.txt
1x OPUS46_FINISH_CRITICAL_PATH_JUDGE_PROMPT.txt
1x OPUS46_CORE_FREEZE_READY_JUDGE_PROMPT.txt

Round 2 goal:
- resolve contradictions created by Round 1
- stop non-causal repeated work
- identify exact remaining blocker
- prepare the smallest path to Codex / Mac physical proof / Core Freeze
- no queue expansion merely to use quota
