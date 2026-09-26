# Courier Universal Wall Long-Run Prompt

Use this as the common copy/paste mission for Mac, Windows, Google/Antigravity CLI and Muse.

Change only the small CONFIG block when needed.

---

COURIER UNIVERSAL WALL LONGRUN

CONFIG
HOST=AUTO
PROVIDER=AUTO
WALL_SIZE=10
RESERVED_INTERACTIVE=2
ROUND_HOURS=4
TASK_SIZE=LARGE
MODE=READ_ONLY_REPORT

GOAL
Do useful Courier work continuously for this bounded round without turning the human into the message bus.

REPOSITORY
Mac: /Users/user/Downloads/2026-courier
Windows: C:\Users\lol\2026-workspace\2026-courier

If neither repo exists:
STATUS=WRONG_HOST
STOP.

CANONICAL COORDINATION
Read current truth from:
- ops/ai/COURIER_SESSION_STATE_2026-09-26.json
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/COURIER_GROWTH_GOALS_2026-09-26.md
- ops/ai/WALL_SCALING_LEDGER_REQUIREMENT_2026-09-26.md
- ops/ai/META_MODEL_API_BILLING_GUARD_2026-09-26.md

CURRENT ACCEPTED REPAIR BASE
candidate-b-1
4c1e24ccc522042af826bc4c2b595daf85d097f9

candidate-b-2 is rejected.
Do not wait for candidate-b-3.
Do not redefine canonical state.

AUTHORITY
Default authority is READ_ONLY_REPORT.

Do not modify source code unless a current durable coordination record explicitly names this exact session/slot as writer for the exact scope.

Windows Antigravity remains the only final-candidate source writer unless durable coordination explicitly changes that.

REPORT WRITES
If the environment already has an established runtime/slots reporting convention, write only inside this session's own report/slot area.
Do not invent a new shared writer architecture during this run.
If report writing is unavailable, keep evidence in the final response.

LOGICAL WALL
WALL_SIZE is requested logical capacity, not a heavy-process count.

This session claims exactly ONE available logical slot inside the requested wall using the repository's existing claim/report convention if present.

Never steal a live slot.
Never duplicate another live slot's current scope.
If ownership is ambiguous, choose a different unowned read-only scope.

RESERVE
RESERVED_INTERACTIVE slots are intentionally left free for human/coordinator use.
Do not consume them for unattended work.

RESOURCE RULES
- host safety outranks throughput
- MAX_HEAVY_JOBS remains whatever the current resource policy proves; current default is 1
- do not start a second heavy job
- no nested agents
- no busy loops
- no tight polling
- no artificial CPU load
- no broad process killing
- no restart/reboot
- no provider/account rotation
- no spend/purchase changes
- do not expose API keys
- if host pressure is significant, downgrade to LIGHT READ ONLY

WORK SIZE
Prefer one coherent LARGE work package over many tiny tasks.

Good LARGE packages:
1. FINAL_CANDIDATE + exact changed-file + test-evidence reconciliation
2. 12 required final-test cases evidence matrix
3. duplicate/replay/lost-ACK safety
4. trusted task-owned artifact/hash chain
5. restart durability + crash windows
6. automatic B eligibility/dispatch proof
7. claim/lease concurrency + stale winner safety
8. persistence/recovery honesty
9. verifier fail-closed/error paths
10. resource/process/thermal safety
11. cross-platform portability
12. stale truth / branch evidence / dead assumptions
13. Ledger gaps from Goal through Reconcile
14. result-harvest/dedup/next-READY analysis

TASK SELECTION
Before starting:
1. read current durable reports/results
2. identify already covered scopes
3. prefer a high-value unowned dependency-safe scope
4. do not redo a clean review just because capacity exists
5. if critical-path work is fully covered, move to the next authorized category
6. idea exploration is allowed only after useful proof work and must remain a minority of the round

CONTINUATION
CONTINUE_BY_DEFAULT=YES

Loop:
READ
-> TRACE
-> VERIFY
-> EVIDENCE
-> RESULT
-> CHECK PEER/LEDGER STATE
-> NEXT UNOWNED SAFE AREA
-> CONTINUE

Do not return to the human after one small task.

ROUND
Target useful work for ROUND_HOURS hours, but stop earlier if:
- no safe authorized work remains
- provider/API unavailable
- ownership becomes ambiguous
- host/resource guard triggers
- money/permission/human gate is reached
- repeated-state/no-progress condition is detected

Do not prolong the run with busywork merely to hit the time target.

EVIDENCE CLASSES
PROVEN_BY_CODE
PROVEN_BY_EXECUTED_TEST
TEST_EXISTS_NOT_EXECUTED
PHYSICAL_PROOF_REQUIRED
STALE
CONTRADICTED
UNKNOWN

TRUTH RULES
- RESULT_RECEIVED != VERIFIED
- mocks != physical proof
- Linux != Windows physical proof
- historical SHA success != newer candidate proof
- no evidence -> no PASS
- changed status/worker/attempt/dispatch/artifact result is not identical replay
- worker-controlled expected hash cannot authorize exact-content success

FINAL CHECKPOINT
Return concise structured output:

SLOT=
HOST=
PROVIDER=
MODE=
ROUND_TARGET_HOURS=
AREAS_CHECKED=
FILES_OR_REFS_READ=
STATUS=CLEAN/FINDING/BLOCKED/UNKNOWN
PROVEN=
NEW_FINDINGS=
CONTRADICTIONS=
MISSING_EVIDENCE=
MISSING_TESTS=
WRITE_REQUIRED=YES/NO
PHYSICAL_PROOF_REQUIRED=YES/NO
CRITICAL_PATH_IMPACT=YES/NO
SAFE_TO_PARK=YES/NO
CENTRAL_WRITER_INPUT=
NEXT_UNCHECKED_AREA=
HOST_RESOURCE_STATUS=
STOP_REASON=

STOP.
