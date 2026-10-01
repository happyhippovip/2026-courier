# WIN-BB-01 PKG-E — Spillover: verifier-fail-closed + restart (role families 2–3)

SHELL=DOWN, static only. Dedupe: MW2 rows 1-7 + MASTER_6C + V-PKG1-1/V-PKG4-3/V-PKG4-5 adopted; only
NEW items filed below. O2 (unguarded daemon loads) cited — not re-filed.

## BB01-NEW-2 (MEDIUM, revenue-lane owner): revenue lane speaks a stale contract end-to-end; verifier revenue branch unreachable via shipped producers

CHAIN (all PROVEN_BY_CODE, files fully read):
(a) scripts/revenue_customer_intake.py:16-34 POSTs {"goal_id","goal_text","tasks":[{task_id,type,
capabilities:[revenue_safety_audit],...}]} to /goals. Server submit_goal (app.py:94-151) reads ONLY
{"goal_text","workflow_plan"}: "tasks" is IGNORED, client "goal_id" is IGNORED (server mints :101),
missing "workflow_plan" → ChiefCommander planner path (:120-147) invents generic steps with NO
capabilities. Intake IDs/tasks never enter the system.
(b) scripts/revenue_worker_adapter.py:95 expects claim_resp["task_id"] TOP-LEVEL. Server returns
{"task": {...}} or {"task": None} (:347/:350) → "task_id" never present → adapter NEVER executes
(silent idle). Its register carries capabilities ["revenue_safety_audit","linux"] (:84) but claim
matching only knows github/mac/windows/linux/antigravity (:286-290), and even a claimed task would
post {task_id,attempt_id,worker_id,result_data,artifact_*} (:132-140) — missing goal_id/dispatch_id/
run_id/result_id/status/artifacts → validate_durable_result raises → 400.
(c) scripts/courier_verifier.py:114 revenue branch requires task.get("capabilities") to contain
"revenue_safety_audit". No server path SETS task capabilities; only verbatim workflow_plan
passthrough (:110-118) could carry them, and no in-repo producer submits such steps. Branch is
reachable ONLY via hand-crafted POST. The branch itself is fail-closed (CalledProcessError→FAIL;
missing script→outer catch→log+retry, never PASS) — the defect is UPSTREAM: deterministic revenue
verification never runs; revenue work (if forced through) falls into the generic artifact path with
planner-invented artifacts.
CENTRAL_WRITER_INPUT: FILE=scripts/revenue_customer_intake.py + scripts/revenue_worker_adapter.py.
REQUIRED_BEHAVIOR (owner picks): either retire the revenue lane (delete adapter+intake+verifier
branch+gh workflow refs) or re-contract it to current server shape (workflow_plan steps with
instruction/target_agent/artifacts/capabilities passthrough; adapter claim .task parsing + durable
result posting). WHY_IT_MATTERS=dead revenue path that LOOKS wired (intake→server→adapter→verifier
all reference each other) but no-ops at every joint; a revenue pilot would silently verify nothing.
TEST_TO_ADD_OR_RUN=intake-shape contract test (intake payload keys ⊆ server-accepted keys) or
adapter-claim parse test against live /tasks/claim response shape. DO_NOT_CHANGE=server
submit_goal/claim/result gates, generic verifier path, intake_dispatcher gh-lane (separate).

## BB01-NEW-3 (LOW, daemon owner): rejected_result_<task_id>.json copies accumulate; same-task overwrite

CODE=windows daemon :346 + mac daemon :573 (symmetric; mac line by search, file not fully read).
BEHAVIOR=every 4xx REJECTED persists a full task+payload copy; zero readers outside tests (search:
only test pins existence); zero rotation/cleanup/expiry anywhere. (1) Unbounded disk growth per
rejection (payloads include stdout/stderr). (2) Filename keys task_id ONLY: resume→retry→REJECTED
again for the same task_id silently OVERWRITES the first copy (evidence loss). REQUIRED=either
cap/rotate (e.g. keep-N per task, or TTL janitor) or key by attempt (rejected_<task>_<attempt>.json).
TEST_TO_ADD=double-reject same task_id after resume → assert both copies exist (RED today).

## Adopted confirmations (cited, no new filing)

- MW2 rows 1-5,7 SAFE/DESIGN-SAFE stand on current disk (ACK paths, RELEASE_PENDING, STARTED-release,
  atomic persist). Row 6 (FAILED-requeue side effects) CONDITIONAL-OPEN = same as MASTER_6C G-C1.
- MW2-X1 (taskkill present) CONTRADICTED on current disk (full re-read: no kill primitives :200-237);
  recorded as revision-churn artifact, not as MW2 error.
- Corrupt current_task.json crash path (load :285-286 outside loop try): consequence analysis would
  overlap O2 (MUSE45_T-O) → left to O2 owner; noted here only as pointer.
