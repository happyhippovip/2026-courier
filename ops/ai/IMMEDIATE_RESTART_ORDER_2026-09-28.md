# Immediate Restart Order — 2026-09-28

Current durable state at creation:
PRE_CODEX_STATE=DURABILITY_PENDING
AUTHORITATIVE_READY=NO
Ledger complete by operator report.

## 1 Windows PC now
1x external PowerShell launcher:
scripts/windows_continuous_autopilot.ps1

Inside it:
ops/ai/WINDOWS_SELFTEST_CONTINUOUS_AUTOPILOT_PROMPT.txt

Additional logical Windows Google slots:
6-10 max, each unique WINDOWS_HNI_02..20 task.
Only one gate-persistence owner.

## 2 Muse now
8-12 logical Muse windows:
ops/ai/MUSE_SELFTEST_CONTINUOUS_DAY_WALL_PROMPT.txt
Each must claim unique C2 work.
No Ledger work.

## 3 Opus 4.6 now
3 windows:
- OPUS46_POST_LEDGER_CRITICAL_PATH_PROMPT.txt
- OPUS46_POST_LEDGER_RUN_PROOF_PROMPT.txt
- OPUS46_POST_LEDGER_CORE_FREEZE_PROMPT.txt

Optional 4th:
- OPUS46_MOTOR_RELIABILITY_JUDGE_PROMPT.txt

## 4 Codex later, not now
Only after:
PRE_CODEX_STATE=READY
AUTHORITATIVE_READY=YES
FINAL_SHA durable
handoff packet exists

Then exactly 1x:
ops/ai/post_ledger_models/CODEX_HIGH_ONCE_FIXED_CANDIDATE_PROMPT.txt

## 5 After Codex green
Mac exact binding
-> one physical RUN_1 owner
-> RUN_1 PASS
-> one physical RUN_2 owner
-> RUN_2 PASS
-> Core Freeze
-> minimum real pilot
-> Product Shell only after positive pilot signal.
