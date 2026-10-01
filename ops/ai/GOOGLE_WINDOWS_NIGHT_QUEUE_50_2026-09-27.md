# Google Windows Night Queue 50 ÔÇö 2026-09-27

Status: ACTIVE COST-SENSITIVE QUEUE
Purpose: 50 logical tasks for a small number of Windows Google workers. This is NOT permission to open 50 windows.

## Hard rules

- No broad repository census.
- No `Get-ChildItem -Recurse` across the repository.
- No "find something useful" loops.
- No rereading unchanged files merely to stay busy.
- Every task has a concrete scope and deliverable.
- Windows Antigravity Central Writer remains the only final-candidate source writer.
- Google workers are READ_ONLY / TARGETED_TEST unless a newer durable authority explicitly changes that.
- MAX_HEAVY_JOBS=1 per host.
- Identical work must not be repeated if a durable result already exists.
- A provider/account/session change never resets task completion.
- Manual account switching, if the user chooses it, must not create duplicate execution.
- Do not automate account rotation or use it to bypass provider limits.

## Durable local queue state

Windows scratch root:

`C:\Users\lol\courier_work\google_night_queue\`

Workers write only there:

- `claims\Q###.claim`
- `results\Q###.result.md`
- `workers\<worker-id>.checkpoint.md`

Source checkout remains untouched.

A task with an existing result file is DONE for queue-selection purposes unless that result explicitly says RETEST_AFTER_FINAL_SHA.

A claim older than 150 minutes with no result may be treated as stale only after confirming no matching live worker owns it.

## Canonical endgame truth

Accepted base:
`candidate-b-1 @ 4c1e24ccc522042af826bc4c2b595daf85d097f9`

Rejected:
`candidate-b-2`

Do not wait for candidate-b-3.

Exact final-writer source scope:

1. scripts/courier_verifier.py
2. scripts/integration_contract.py
3. tests/test_artifact_upload_flow.py
4. server/app.py
5. tests/test_p3_server_idempotency.py

Trusted-content rule:
task/workflow-owned expected_sha256 is authoritative. Worker-controlled expected_sha256 must never create exact-content success.

Duplicate rule:
duplicate ACK only for the same canonical result in the same attempt and dispatch generation.

Physical proof:
RUN_1 then RUN_2 only after a green final candidate and independent review.

## Queue

### P0 ÔÇö Final candidate defects / exact semantics

Q001 ÔÇö CURRENT_FINAL_HEAD
Scope: git metadata only.
Do: identify current final-writer branch/SHA if present; do not scan source.
Done: one-line candidate SHA/base/scope status.

Q002 ÔÇö FINAL_SCOPE_DIFF
Scope: git diff names against candidate-b-1 only.
Done: EXACT_5_FILES=YES/NO plus unexpected/missing names.

Q003 ÔÇö VERIFIER_EXPECTED_ARTIFACT_COVERAGE
Files: scripts/courier_verifier.py, tests/test_artifact_upload_flow.py
Do: determine whether all task-declared expected artifacts must be present in result.
Done: concrete defect/test evidence; no patch.

Q004 ÔÇö OMISSION_BYPASS_TEST
File: tests/test_artifact_upload_flow.py
Do: locate or design one targeted test proving worker omission cannot bypass a task-owned expectation.
Done: exact test name/fixture/assertions for Central Writer.

Q005 ÔÇö CORRECT_SERVER_BYTES
Files: scripts/courier_verifier.py, tests/test_artifact_upload_flow.py
Done: identify exact test/evidence for correct server bytes PASS.

Q006 ÔÇö WRONG_SERVER_BYTES
Same files.
Done: identify exact test/evidence for wrong server bytes FAIL.

Q007 ÔÇö WORKER_EXPECTED_HASH_REJECTION
Files: scripts/integration_contract.py, scripts/courier_verifier.py, tests/test_artifact_upload_flow.py
Done: prove worker-controlled expected_sha256 cannot cause exact-content success. Do not "fix" by trusting worker input.

Q008 ÔÇö WORKER_EXPECTED_HASH_OMISSION
Same files.
Done: prove omission of worker expected_sha256 cannot bypass trusted task expectation.

Q009 ÔÇö LEGACY_NO_TASK_EXPECTATION
Same files.
Done: verify missing task-owned expectation remains legacy/not exact-content.

Q010 ÔÇö MALFORMED_TARGET_FAIL_CLOSED
Same files.
Done: verify malformed or ambiguous artifact target fails closed.

Q011 ÔÇö VERIFIER_POISON_PILL
Files: scripts/courier_verifier.py, tests/test_artifact_upload_flow.py
Do: check whether one malformed task can prevent later tasks from being processed.
Done: exact code region + smallest targeted test needed.

Q012 ÔÇö RESULT_SCHEMA_BOUNDARY
Files: scripts/integration_contract.py, tests/test_artifact_upload_flow.py
Do: reconcile result artifact schema with the trusted-content rule. The worker result must not be granted task-owned authority.
Done: exact required contract behavior + test; do not broaden schema blindly.

### P0 ÔÇö Replay/idempotency

Q013 ÔÇö IDENTICAL_REPLAY_ACK
Files: server/app.py, tests/test_p3_server_idempotency.py
Done: same canonical result/same attempt/same dispatch => duplicate ACK evidence.

Q014 ÔÇö REPLAY_AFTER_RELOAD
Same files.
Done: persistence/reload evidence for identical replay.

Q015 ÔÇö CHANGED_STATUS_REJECT
Same files.
Done: changed status is not duplicate success.

Q016 ÔÇö CHANGED_WORKER_REJECT
Same files.
Done: changed worker is not duplicate success.

Q017 ÔÇö CHANGED_ATTEMPT_REJECT
Same files.
Done: changed attempt is rejected/not duplicate success.

Q018 ÔÇö CHANGED_DISPATCH_REJECT
Same files.
Done: changed dispatch generation is rejected/not duplicate success.

Q019 ÔÇö CHANGED_ARTIFACT_REJECT
Same files.
Done: changed artifact result is not duplicate success.

Q020 ÔÇö RESULT_IDENTITY_TARGET_TEST
Files: tests/test_result_identity_binding.py, server/app.py
Do: run only the exact relevant test(s), not a suite.
Done: command + pass/fail + failure excerpt if any.

### P0 ÔÇö Final candidate test gate

Q021 ÔÇö ARTIFACT_TARGETED_TEST_FILE
File: tests/test_artifact_upload_flow.py
Do: run only this file after a new final SHA exists.
Done: exact command/count/pass/fail; RETEST_AFTER_FINAL_SHA if no new candidate.

Q022 ÔÇö IDEMPOTENCY_TARGETED_TEST_FILE
File: tests/test_p3_server_idempotency.py
Same rule.

Q023 ÔÇö RESULT_IDENTITY_TARGETED_TEST_FILE
File: tests/test_result_identity_binding.py
Same rule.

Q024 ÔÇö PY_COMPILE_FIVE_SCOPE
Files: only the Python modules in final scope.
Do: py_compile only relevant modules after new final SHA.
Done: command/result.

Q025 ÔÇö DIFF_CHECK_FINAL
Scope: git diff --check against final candidate only.
Done: pass/fail and exact offending lines if any.

Q026 ÔÇö EXACT_12_CASE_MATRIX
Inputs: results Q003-Q019 plus current five-file candidate.
Do: synthesize only; do not reread source unless one referenced result is missing.
Done: cases 1..12 with PASS_EXECUTED/PASS_CODE/FAIL/UNKNOWN.

Q027 ÔÇö CENTRAL_WRITER_FIX_PACKET
Inputs: failed P0 results only.
Do: deduplicate defects into one exact writer packet.
Done: FILE/FUNCTION/GAP/REQUIRED_BEHAVIOR/TEST_NEEDED/DO_NOT_CHANGE.

Q028 ÔÇö FINAL_SHA_GATE
Scope: git metadata + Q021-Q027 results.
Done: FINAL_SHA, exact five files, tests green/no-skips YES/NO.

### P1 ÔÇö Mac physical proof preparation, no execution

Q029 ÔÇö MAC_SUPERVISOR_BINDING
File: scripts/mac_worker/muse_supervisor.py
Do: locate exact invocation/binding inputs needed by RUN_1.
Done: concise command template, no execution.

Q030 ÔÇö RUN1_ISOLATED_PORT
Inputs: Mac supervisor file + existing RUN_1 docs only.
Done: exact isolation/port requirement.

Q031 ÔÇö RUN1_DISTINCT_CREDENTIAL_ROLES
Inputs: Mac supervisor/config docs only.
Done: worker vs verifier credential binding requirement; no secrets.

Q032 ÔÇö RUN1_A_EXECUTION_COUNT
Inputs: final tests/runtime code only as needed.
Done: how to prove A executed exactly once.

Q033 ÔÇö RUN1_SERVER_BYTES_PROOF
Inputs: verifier/runtime code only as needed.
Done: exact evidence showing downloaded server bytes match task-owned SHA.

Q034 ÔÇö RUN1_AUTO_B_PROOF
Inputs: READY/dispatch code only as needed.
Done: exact evidence that B auto-dispatches after A reconciliation.

Q035 ÔÇö RUN1_FAILED_INVALIDATES
Inputs: current canary rules + runtime failure path.
Done: prove any FAILED execution invalidates RUN_1.

Q036 ÔÇö RUN1_ZERO_HUMAN_RELAY
Inputs: proof policy only.
Done: exact evidence fields proving human relay count 0.

Q037 ÔÇö RUN2_RESULT_PERSISTENCE
Inputs: persistence/restart code only as needed.
Done: proof that A result survives controlled restart.

Q038 ÔÇö RUN2_NO_A_REEXECUTION
Inputs: restart/runtime code only.
Done: exact evidence required for no A replay.

Q039 ÔÇö RUN2_POST_RESTART_RECONCILE
Inputs: verifier/reconcile path only.
Done: exact evidence A reconciles after restart and B proceeds.

Q040 ÔÇö MAC_PREFLIGHT_PACKET
Inputs: Q029-Q039 only.
Do: synthesize; no new repo read unless a referenced result is missing.
Done: RUN1_READY / RUN2_READY gates and exact blockers.

### P1 ÔÇö Automation/system continuation

Q041 ÔÇö LEDGER_IDENTITY_CHAIN
Files: scripts/integration_contract.py plus canonical ledger docs only.
Done: Goal->Task->Attempt->Dispatch->Result->Verify->Reconcile field map.

Q042 ÔÇö RESULT_HARVEST_DEDUP
Inputs: queue result files + returned-result policy.
Done: rule for deduplicating worker findings without rereading source.

Q043 ÔÇö NEXT_READY_SELECTION
Inputs: ledger/queue policies only.
Done: deterministic next-READY rule; no "find work" scan.

Q044 ÔÇö ACCOUNT_SESSION_CONTINUITY
Inputs: subscription-first router + this queue policy.
Done: rule that manual authorized account/session changes preserve queue/result state and never rerun completed tasks.

Q045 ÔÇö NO_BROAD_READ_COST_GUARD
Inputs: current overnight prompt policy.
Done: exact guardrails forbidding recursive scans/repeated unchanged reads/idle analysis.

Q046 ÔÇö NONINTERFERENCE_WORKER_CLAIMS
Inputs: this queue policy.
Done: verify claim/result layout prevents two live workers taking same QID; identify any race gap.

Q047 ÔÇö DEVICE_ADMISSION_NIGHT_RULE
Inputs: DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md
Done: night rule for requested/admitted/active/guarded without opening more windows.

Q048 ÔÇö SUBSCRIPTION_FIRST_ROUTE
Inputs: SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md
Done: subscription-first/PAYG-explicit fallback rule integrated with queue continuation.

Q049 ÔÇö MORNING_HANDOFF
Inputs: all completed Q### result files only.
Do: synthesize; no source reread.
Done: FINAL_SHA/TESTS/RUN1/RUN2/OPEN/BLOCKED/NEXT.

Q050 ÔÇö QUEUE_COMPLETION_AUDIT
Inputs: claims/results directory only.
Do: list completed, blocked, stale-claim, remaining-ready IDs.
Done: one concise queue state; no repo scan.

## Selection rule

Always claim the smallest-numbered READY task whose result does not already exist.

Do not repeat a task because a new session/account starts.

If a dependency is not ready, skip to the next READY task.

If Q028 reports a green final candidate, prioritize Q029-Q040.

If a task produces a defect, Q027 is the only writer-packet aggregation task; workers must not each produce redundant full-repo reports.

When no READY tasks remain, checkpoint and stop. Do not invent work.
