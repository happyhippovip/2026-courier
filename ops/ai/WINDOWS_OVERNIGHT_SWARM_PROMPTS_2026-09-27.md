> **SUPERSEDED FOR COST-SENSITIVE GOOGLE NIGHT WORK (2026-09-27):** Do not use the broad read/trace loops below for current overnight Google work. Use `GOOGLE_WINDOWS_NIGHT_QUEUE_50_2026-09-27.md` with `GOOGLE_WINDOWS_NIGHT_WORKER_BOOTSTRAP_2026-09-27.txt`. Completed tasks must survive session/account changes and must not be rediscovered.\n\n# Windows Overnight Swarm Prompts — 2026-09-27

Status: OPERATIONAL PROMPT PACK  
Purpose: run many Windows CLI/Muse windows overnight without turning logical capacity into uncontrolled heavy-process concurrency.

## Global invariant

Many windows may exist, but heavy work remains separately admitted.

- MAX_HEAVY_JOBS=1 unless a newer proven resource policy changes it.
- Every session is READ_ONLY_REPORT by default.
- Windows Antigravity/Central Writer remains the only final-candidate source writer unless durable coordination explicitly changes ownership.
- Prefer smooth stable throughput over maximum window count.
- If host pressure rises, stop admitting new work and let sessions switch to LIGHT mode.
- Checkpoint -> clear stale context -> reload minimal truth -> continue.

## Google / Antigravity CLI long-run prompt (for many windows)

Use the same prompt in many independent CLI windows.
Each session must claim one unique logical slot.

WINDOWS GOOGLE OVERNIGHT WORKER

HOST=WINDOWS
PROVIDER=GOOGLE_CLI
MODE=READ_ONLY_REPORT
ROUND_HOURS=10
TASK_SIZE=LARGE
WALL_NAMESPACE=GWIN
REQUESTED_GOOGLE_SLOTS=50
RESERVED_INTERACTIVE=5

REPO=C:\Users\lol\2026-workspace\2026-courier

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
GWIN-001..GWIN-050

Never steal a live slot.
Never duplicate another live scope.
If slot ownership is ambiguous, choose another unowned slot.

AUTHORITY:
READ_ONLY_REPORT
NO source writes
NO commits
NO push/merge/rebase
NO branch creation
NO server/worker start
NO physical Canary
NO broad/heavy test suites
NO nested agents
NO account rotation
NO spend changes

RESOURCE:
MAX_HEAVY_JOBS=1 globally.
This worker should stay LIGHT unless explicitly admitted.
On CPU/RAM/pagefile/thermal pressure: do not start new work; switch to LIGHT read-only.

TASK SELECTION:
Choose the highest-value unowned LARGE package from:
1 final-candidate/test-evidence reconciliation
2 12-case acceptance evidence matrix
3 duplicate/replay/lost-ACK
4 trusted task-owned artifact/hash chain
5 restart durability/crash windows
6 automatic B dispatch
7 claim/lease concurrency
8 persistence/recovery honesty
9 verifier fail-closed/error paths
10 resource/process safety
11 cross-platform portability
12 stale truth/branch evidence
13 Ledger gaps Goal->Reconcile
14 result-harvest/dedup/next READY

CONTINUE_BY_DEFAULT=YES

Loop:
READ -> TRACE -> VERIFY -> EVIDENCE -> RESULT
-> RECHECK PEERS/LEDGER
-> NEXT UNOWNED SAFE AREA
-> CONTINUE

After each meaningful package:
checkpoint durable result.
If old context no longer affects the next decision:
CLEAR/ROTATE
then reload only minimal current truth.

Never create busywork to fill time.

STOP EARLY only for:
NO_SAFE_READY_WORK
PROVIDER_UNAVAILABLE
RESOURCE_GUARD
COST_OR_QUOTA_GUARD
OWNERSHIP_AMBIGUITY
HUMAN_MONEY_PERMISSION_GATE
REPEATED_STATE_NO_PROGRESS

RETURN:
SLOT=
AREAS_CHECKED=
STATUS=
PROVEN=
NEW_FINDINGS=
CONTRADICTIONS=
MISSING_EVIDENCE=
MISSING_TESTS=
CRITICAL_PATH_IMPACT=
SAFE_TO_PARK=
CENTRAL_WRITER_INPUT=
NEXT_UNCHECKED_AREA=
HOST_RESOURCE_STATUS=
STOP_REASON=

STOP.

## Muse Windows long-run prompt (10 windows)

WINDOWS MUSE OVERNIGHT WORKER

HOST=WINDOWS
PROVIDER=MUSE
MODE=READ_ONLY_REPORT
ROUND_HOURS=10
TASK_SIZE=LARGE
WALL_NAMESPACE=MWIN
REQUESTED_MUSE_SLOTS=10
RESERVED_INTERACTIVE=2

REPO=C:\Users\lol\2026-workspace\2026-courier

Read:
origin/coordination/autofill-task-seed-20260926:
ops/ai/COURIER_SESSION_STATE_2026-09-26.json
ops/ai/RETURNED_RESULT_POLICY.md
ops/ai/WALL_CONTROL_INDEX_2026-09-26.md
ops/ai/OVERNIGHT_WALL_10H_POLICY_2026-09-26.md
ops/ai/CONTEXT_HYGIENE_AND_HANDOFF_POLICY_2026-09-26.md
ops/ai/LARGE_WORK_PACKAGES_2026-09-26.md

Claim exactly ONE:
MWIN-01..MWIN-10

Never duplicate peer scope.

READ_ONLY_REPORT.
Windows Antigravity remains the only final-candidate source writer.
No source writes.
No commits/push/merge/rebase.
No heavy suite.
No physical Canary.
No nested agents.
No spend/account changes.

MAX_HEAVY_JOBS=1 globally.

Prefer these Muse roles:
MWIN-01 Ledger Integrity
MWIN-02 Duplicate/Replay
MWIN-03 Trusted Artifact Truth
MWIN-04 Restart Durability
MWIN-05 Auto-B Dispatch
MWIN-06 Claim/Lease Concurrency
MWIN-07 Failure Semantics
MWIN-08 Resource/Process Safety
MWIN-09 Stale Truth / Branch Reconciliation
MWIN-10 Product Truth / Grandma Test

CONTINUE_BY_DEFAULT=YES

After a meaningful package:
checkpoint -> clear stale context -> reload minimal truth -> continue.

Return concise evidence only.

STOP.

## Quick free Windows CLI prompt

Keep several windows free for coordinator work.

COURIER WINDOWS QUICK FREE SLOT

HOST=WINDOWS
MODE=READ_ONLY
TIMEBOX_MINUTES=15

Read current coordination truth and current peer reports.

Pick exactly ONE high-value unowned question that can be answered in 10-15 minutes without:
source writes
heavy tests
servers/workers
physical Canary
new agents
branch changes

Priority:
1 verify a current critical-path claim
2 close one evidence gap
3 detect one stale/contradictory assumption
4 verify one peer finding
5 identify one missing targeted test

Return only:
TASK=
WHY_NOW=
EVIDENCE=
VERDICT=
CRITICAL_PATH_IMPACT=
NEXT_ACTION=

STOP.
