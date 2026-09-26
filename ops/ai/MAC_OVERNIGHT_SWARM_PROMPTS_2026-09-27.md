# Mac Overnight Swarm Prompts — 2026-09-27

Status: OPERATIONAL PROMPT PACK
Purpose: let many Mac Google CLI and Muse windows work for up to 10 hours without returning after one small task.

## Global rule

100 logical slots are allowed as a coordination namespace.

This does NOT mean 100 heavy resident processes should be opened at once.

Prefer smooth verified throughput over maximum visible concurrency.

Current safety invariant:
MAX_HEAVY_JOBS=1

All sessions default to READ_ONLY_REPORT unless durable coordination explicitly grants an exact writer scope.

Every long-running session must:
CHECKPOINT -> CLEAR STALE CONTEXT -> RELOAD MINIMAL TRUTH -> CONTINUE

Do not return to the human after one completed subtask while useful dependency-safe authorized work remains.

Do not invent busywork to fill the 10-hour target.

---

## MAC GOOGLE CLI 100-SLOT OVERNIGHT WORKER

HOST=MAC
PROVIDER=GOOGLE_CLI
MODE=READ_ONLY_REPORT
ROUND_HOURS=10
TASK_SIZE=LARGE
WALL_NAMESPACE=GMAC
REQUESTED_GOOGLE_SLOTS=100

REPO=/Users/user/Downloads/2026-courier

Read current truth from:
origin/coordination/autofill-task-seed-20260926

Load:
ops/ai/COURIER_SESSION_STATE_2026-09-26.json
ops/ai/RETURNED_RESULT_POLICY.md
ops/ai/WALL_CONTROL_INDEX_2026-09-26.md
ops/ai/OVERNIGHT_WALL_10H_POLICY_2026-09-26.md
ops/ai/CONTEXT_HYGIENE_AND_HANDOFF_POLICY_2026-09-26.md
ops/ai/LARGE_WORK_PACKAGES_2026-09-26.md

CLAIM:
Claim exactly ONE free logical slot:
GMAC-001..GMAC-100

Never steal a live slot.
Never duplicate another live scope.

ROLE AUTO-SELECTION BY SLOT NUMBER:

001-010 FINAL_CANDIDATE_AND_TEST_EVIDENCE
011-020 TWELVE_CASE_ACCEPTANCE_MATRIX
021-030 DUPLICATE_REPLAY_LOST_ACK
031-040 TRUSTED_ARTIFACT_HASH_CHAIN
041-050 RESTART_DURABILITY_CRASH_WINDOWS
051-060 AUTO_B_ELIGIBILITY_AND_DISPATCH
061-070 CLAIM_LEASE_CONCURRENCY
071-080 RESOURCE_PROCESS_PORTABILITY
081-090 STALE_TRUTH_BRANCH_RECONCILIATION
091-100 RESULT_HARVESTER_LEDGER_GAPS_PRODUCT_TRUTH

AUTHORITY:
READ_ONLY_REPORT

NO source writes
NO commits
NO push/merge/rebase
NO branch creation
NO physical Canary
NO server/worker start
NO broad test suites
NO nested agents
NO account rotation
NO spend changes
NO destructive process control

Windows Antigravity remains the only final-candidate source writer unless durable coordination explicitly changes ownership.

RESOURCE:
MAX_HEAVY_JOBS=1 globally.
This worker should remain LIGHT unless explicitly admitted.
If CPU/RAM/swap/thermal pressure rises:
STOP ADMITTING NEW WORK
switch this session to LIGHT READ ONLY
checkpoint current result

CONTINUE_BY_DEFAULT=YES

LOOP:
READ
-> TRACE
-> VERIFY
-> EVIDENCE
-> RESULT
-> CHECKPOINT
-> RECHECK LEDGER/PEERS
-> NEXT UNOWNED SAFE AREA IN SAME ROLE FAMILY
-> CONTINUE

If same role family is exhausted:
move to the next unowned authorized role family.

After each meaningful package:
if old context no longer changes the next decision:
CLEAR/ROTATE CONTEXT
reload only current coordination + exact next task
continue.

Do not return after one task.

STOP EARLY only for:
NO_SAFE_READY_WORK
PROVIDER_UNAVAILABLE
RESOURCE_GUARD
COST_OR_QUOTA_GUARD
OWNERSHIP_AMBIGUITY
HUMAN_MONEY_PERMISSION_GATE
REPEATED_STATE_NO_PROGRESS

FINAL:
SLOT=
ROLE_FAMILY=
PACKAGES_COMPLETED=
PROVEN=
NEW_FINDINGS=
CONTRADICTIONS=
MISSING_EVIDENCE=
MISSING_TESTS=
CRITICAL_PATH_IMPACT=
CENTRAL_WRITER_INPUT=
NEXT_UNCHECKED_AREA=
HOST_RESOURCE_STATUS=
STOP_REASON=

STOP.

---

## MAC MUSE 100-SLOT OVERNIGHT WORKER

HOST=MAC
PROVIDER=MUSE
MODE=READ_ONLY_REPORT
ROUND_HOURS=10
TASK_SIZE=LARGE
WALL_NAMESPACE=MMAC
REQUESTED_MUSE_SLOTS=100

REPO=/Users/user/Downloads/2026-courier

Read current truth from:
origin/coordination/autofill-task-seed-20260926

Load:
ops/ai/COURIER_SESSION_STATE_2026-09-26.json
ops/ai/RETURNED_RESULT_POLICY.md
ops/ai/WALL_CONTROL_INDEX_2026-09-26.md
ops/ai/OVERNIGHT_WALL_10H_POLICY_2026-09-26.md
ops/ai/CONTEXT_HYGIENE_AND_HANDOFF_POLICY_2026-09-26.md
ops/ai/LARGE_WORK_PACKAGES_2026-09-26.md
ops/ai/MUSE_STARTUP_AND_CLEAR_RULE_2026-09-26.md

CLAIM:
Claim exactly ONE free logical slot:
MMAC-001..MMAC-100

Never duplicate peer scope.

ROLE AUTO-SELECTION:

001-010 LEDGER_INTEGRITY
011-020 DUPLICATE_REPLAY
021-030 TRUSTED_ARTIFACT_TRUTH
031-040 RESTART_DURABILITY
041-050 AUTO_B_DISPATCH
051-060 CLAIM_LEASE_CONCURRENCY
061-070 FAILURE_SEMANTICS
071-080 RESOURCE_PROCESS_SAFETY
081-090 STALE_TRUTH_BRANCH_RECONCILIATION
091-100 PRODUCT_TRUTH_RESULT_HARVESTER

AUTHORITY:
READ_ONLY_REPORT

NO source writes
NO commits
NO push/merge/rebase
NO physical Canary
NO broad/heavy suite
NO nested agents
NO account rotation
NO spend changes
NO destructive process control

MAX_HEAVY_JOBS=1 globally.

CONTINUE_BY_DEFAULT=YES

LOOP:
READ
-> TRACE
-> VERIFY
-> EVIDENCE
-> RESULT
-> CHECKPOINT
-> RECHECK PEERS
-> NEXT UNOWNED SAFE AREA
-> CONTINUE

Do not return after one small task.

When context becomes stale/heavy:
checkpoint durable evidence
/clear or fresh session
reload minimal current truth
continue same logical slot/task family.

STOP EARLY only for:
NO_SAFE_READY_WORK
PROVIDER_UNAVAILABLE
RESOURCE_GUARD
COST_OR_QUOTA_GUARD
OWNERSHIP_AMBIGUITY
HUMAN_MONEY_PERMISSION_GATE
REPEATED_STATE_NO_PROGRESS

FINAL:
SLOT=
ROLE_FAMILY=
PACKAGES_COMPLETED=
PROVEN=
NEW_FINDINGS=
CONTRADICTIONS=
MISSING_EVIDENCE=
CRITICAL_PATH_IMPACT=
CENTRAL_WRITER_INPUT=
NEXT_UNCHECKED_AREA=
HOST_RESOURCE_STATUS=
STOP_REASON=

STOP.

---

## MAC QUICK FREE CLI SLOT

HOST=MAC
MODE=READ_ONLY
TIMEBOX_MINUTES=15

Read current coordination truth and peer reports.

Pick exactly ONE high-value unowned question.

Priority:
1 verify critical-path claim
2 close evidence gap
3 detect stale/contradictory assumption
4 verify peer finding
5 identify missing targeted test

NO source writes.
NO heavy tests.
NO server/worker start.
NO physical Canary.
NO nested agents.

Return:
TASK=
WHY_NOW=
EVIDENCE=
VERDICT=
CRITICAL_PATH_IMPACT=
NEXT_ACTION=

STOP.
