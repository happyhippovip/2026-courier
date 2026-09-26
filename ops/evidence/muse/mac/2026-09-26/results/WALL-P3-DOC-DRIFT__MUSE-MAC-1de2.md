# WALL-P3-DOC-DRIFT report

TASK_ID=WALL-P3-DOC-DRIFT
STATUS=DONE
WORKER_ID=MUSE-MAC-1de2
MODE=READ_ONLY (reads only; zero source writes)

NEW_EVIDENCE=PARTIAL — 5 samples checked against writer tip 332a42f9:
3 code-level contract drifts confirmed (all corroborate E30 triple-dead),
2 samples consistent (no drift).

FILE_LINE_EVIDENCE=
1. DRIFT — intake/server param mismatch:
   scripts/revenue_customer_intake.py:19 posts goal_payload with "tasks" list;
   server/app.py:104 branches only on "workflow_plan" in data -> audit params
   silently dropped into planner path. (E30 item 1 reconfirmed.)
2. DRIFT — claim envelope mismatch:
   server/app.py:338 returns jsonify({"task": next_task});
   scripts/revenue_worker_adapter.py:95 tests `"task_id" in claim_resp` (top level)
   -> never true; adapter never sees claimed tasks, server holds DISPATCHED +
   worker busy = wedge. (E30 item 2 reconfirmed.)
3. DRIFT — result identity shortfall:
   scripts/revenue_worker_adapter.py:133-140 res_payload carries 7 fields
   (task_id, attempt_id, worker_id, result_data, artifact_name, artifact_sha256,
   artifact_content_base64); scripts/integration_contract.py:120-130 requires 9
   (goal_id, task_id, attempt_id, dispatch_id, worker_id, run_id, result_id,
   status, artifacts) -> validate_durable_result raises, app.py:366-367 returns
   400 before verdict. (E30 item 3 reconfirmed.)
4. CONSISTENT — README.md:94 `python3 dashboard/server.py`: dashboard/server.py
   exists on tip (last touch dfa65a6b). No drift.
5. CONSISTENT (nuance) — E07:10 "server attempt/dispatch binding (stale rejected)":
   binding enforced at integration_contract.py:138-140 (mismatch -> ContractError);
   staleness path app.py:422-430 quarantines to HUMAN_REQUIRED + BLOCKED rather
   than "rejecting" the post. Claim directionally correct; mechanism is quarantine,
   not rejection.

PROVEN=Samples 1-3 drift present on tip SHA 332a42f9 with exact lines; samples 4-5
show no doc/code contradiction.
UNKNOWN=
- Whether writer has uncommitted local fixes (working tree shows only runtime-state
  files modified: central_state.json, worker.log, snapshot-current.json — untouched).
- Full-doc sweep (5-sample scope per assignment; not exhaustive).

BLOCKER=None for this task.
RECOMMENDED_NEXT=Writer fixes samples 1-3 (same minimal shapes as WALL-P0-VERIFY-400
report: poster builds full DurableResult identity; intake posts workflow_plan or
server accepts tasks list; adapter reads claim_resp["task"]). No doc edits needed
for samples 4-5.
