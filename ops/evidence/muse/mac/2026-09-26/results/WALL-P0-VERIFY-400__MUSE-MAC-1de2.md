# WALL-P0-VERIFY-400 report

TASK_ID=WALL-P0-VERIFY-400
STATUS=DONE
WORKER_ID=MUSE-MAC-1de2
MODE=READ_ONLY (git show / static reads only; zero source writes)

NEW_EVIDENCE=YES — 400-before-verdict still present on writer tip.
Writer tip = origin/agent/canonical-wall-supervisor-v2 = 332a42f9edcf1de1535870592da34a7961880991,
identical to local HEAD (git rev-parse both, diff-stat empty). No newer commit on the line.

FILE_LINE_EVIDENCE=
- server/app.py:365 `durable_result = validate_durable_result(task, data)`
- server/app.py:366-367 `except ContractError as exc: return jsonify({"error": str(exc)}), 400`
- scripts/integration_contract.py:120-130 `required = {goal_id, task_id, attempt_id,
  dispatch_id, worker_id, run_id, result_id, status, artifacts}` (+ run_attempt if present)
- scripts/integration_contract.py:136-137 missing fields raise before any verdict path
- Verdict path unreachable on 400: task never reaches RESULT_RECEIVED (app.py:368),
  so /verify never sees it. 400 fires strictly before verdict.
- Corroborates E30 item 3 (muse_evening_pool/reports/E30_REVENUE_TRIPLE_DEAD.md):
  res_payload lacks goal_id/dispatch_id/run_id/result_id/status/artifacts -> every post 400s.

PROVEN=
1. 400-before-verdict present on writer tip 332a42f9 (exact SHA match both refs).
2. Failure is deterministic for any poster omitting identity fields (contract raises on
   first missing field; real poster revenue_worker_adapter res_payload omits 6 of 9).
3. Side effect: 400 leaves task DISPATCHED with worker still bound -> wedge compounds
   E30 item 2 (adapter never sees claim due to {"task": {...}} envelope).

UNKNOWN=
- Whether writer intends client-side (poster) or server-side (derive/default identity) fix.
- Whether /verify has additional preconditions beyond RESULT_RECEIVED (not read this task).

BLOCKER=None for this task. BLOCKER FOR CANDIDATE: unchanged — no live revenue result
can pass /tasks/result until poster sends full DurableResult identity.

RECOMMENDED_NEXT (minimal fix shape, no code — writer lane owns implementation):
1. Writer fixes the result poster to build res_payload via the existing
   scripts/integration_contract.py:100-111 identity helper (copies goal/task/attempt/
   dispatch/worker ids from claimed task, adds run_id/result_id/status/artifacts),
   instead of hand-building res_payload. Single client-side choke point.
2. Optional hardening (server, writer decision): on ContractError 400, do not leave
   worker bound forever — surface missing-field list (already in error string) to logs.
3. Re-verify with one read-only POST-shape check after writer ships; no re-architecture.
