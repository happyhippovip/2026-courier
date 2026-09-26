# WALL-P1-RESTART-MATRIX report

TASK_ID=WALL-P1-RESTART-MATRIX
STATUS=DONE
WORKER_ID=MUSE-MAC-1de2
MODE=READ_ONLY (static reads only; no restarts performed, no workers touched)

NEW_EVIDENCE=YES — three restart scenarios derived from writer-tip code
(HEAD 332a42f9, server/app.py). MV006 prereq scenarios not found in any pool
reports (grep MV006 empty) -> scenarios built from code truth, marked accordingly.

FILE_LINE_EVIDENCE (all server/app.py @332a42f9)=
- State backend file + atomic: :10 STATE_FILE=server/state/central_state.json;
  :54-56 load_state reads file; :65-71 save via tmp + os.replace.
- Register mismatch: :189-202 worker re-registers with different current_task ->
  task HUMAN_REQUIRED + recovery_reason WORKER_RESTARTED_AND_LOST_STATE, goal BLOCKED.
- Stale reclaim: :402-435 /tasks/reclaim_stale; :417-418 comment "replaying it would
  risk a duplicate effect"; :422-430 DISPATCHED on stale worker -> HUMAN_REQUIRED +
  STALE_WORKER_EFFECT_AMBIGUOUS, goal BLOCKED; :440 returns reclaimed_tasks 0 always.
- Result gate: :365-367 validate -> 400 stays pre-verdict; :368 RESULT_RECEIVED;
  :467-468 /verify requires RESULT_RECEIVED else 409.
- Verdict terminal: :490 status RECONCILED only inside /verify; :462-465
  RECONCILED + same result_id -> ACK_DUPLICATE, else 409.
- Redelivery guards: :356-357 IGNORED for RECONCILED/FAILED_TERMINAL/RESULT_RECEIVED;
  :360-361 ACK_DUPLICATE on same result_id.
- No RESULT_READY state exists in app.py (grep: zero hits).

## Scenario 1 — RESULT_RECEIVED-before-VERIFY + server restart
START_STATE: task RESULT_RECEIVED with task.result persisted (app.py:368-369).
INTERRUPTION: server process dies/restarts before any POST /tasks/verify.
EXPECTED_SAFE_STATE: after restart, load_state (:54-56) restores RESULT_RECEIVED +
result from central_state.json (atomic replace :65-71 prevents torn writes);
GET /tasks/pending_verification (:442-450) still lists it; /verify accepts verdict.
FORBIDDEN_REPLAY: worker MUST NOT re-POST /tasks/result (would return IGNORED,
:356-357) and MUST NOT re-execute the effect; verifier proceeds from persisted result.
PASS_CRITERIA: /verify with matching result_id/artifacts returns verdict-ACK and task
reaches RECONCILED (:490); no duplicate effect observed; no HUMAN_REQUIRED raised.

## Scenario 2 — RESULT redelivery unreachable (no RESULT_READY state)
START_STATE: task RECONCILED (or RESULT_RECEIVED awaiting verify).
INTERRUPTION: worker, unsure its result landed, re-POSTs /tasks/result (redelivery).
EXPECTED_SAFE_STATE: redelivery is unreachable-by-design — there is no RESULT_READY
or re-accept path: RECONCILED + same result_id -> ACK_DUPLICATE (:464-465);
RESULT_RECEIVED (+same result_id) -> ACK_DUPLICATE (:360-361) else IGNORED (:356-357).
State never regresses to DISPATCHED/QUEUED via this path.
FORBIDDEN_REPLAY: server MUST NOT re-queue or re-dispatch on redelivery; worker MUST
NOT treat ACK_DUPLICATE/IGNORED as failure requiring re-execution.
PASS_CRITERIA: redelivery returns ACK_DUPLICATE or IGNORED; task status unchanged;
exactly one verdict recorded in task.verification.

## Scenario 3 — STARTED-ambiguity (worker restart mid-execution)
START_STATE: task DISPATCHED to worker W (or W holds current_task).
INTERRUPTION: W restarts, loses in-memory state. Two sub-cases in code:
(a) W re-registers with different/no current_task -> :189-202 task HUMAN_REQUIRED,
    WORKER_RESTARTED_AND_LOST_STATE, goal BLOCKED.
(b) W stays silent >300s -> /tasks/reclaim_stale :422-430 task HUMAN_REQUIRED,
    STALE_WORKER_EFFECT_AMBIGUOUS, goal BLOCKED, reclaimed_tasks 0.
EXPECTED_SAFE_STATE: HUMAN_REQUIRED + goal BLOCKED in both sub-cases; effect treated
as ambiguous — never auto-replayed (:417-418).
FORBIDDEN_REPLAY: no automatic re-dispatch of the ambiguous task; human (or later
authorized flow) decides after effect inspection.
PASS_CRITERIA: task lands HUMAN_REQUIRED with the correct recovery_reason for the
sub-case; goal BLOCKED; worker record cleared (current_task None :432-434 in case b);
zero duplicate effects.

PROVEN=All transitions above are code-verified at pinned SHA 332a42f9 with file:line.
UNKNOWN=
- MV006 prereq scenarios (not found; scenarios here are code-derived substitutes).
- Live runtime behavior (no restarts executed per FORBIDDEN_ACTIONS; Mac Antigravity
  physical-proof runner owns live validation).
- Whether candidate branches add a RESULT_READY state elsewhere (app.py has none).

BLOCKER=None for this task.
RECOMMENDED_NEXT=Hand scenarios 1-3 to Mac physical-proof runner for live validation
when authorized; writer owns any code change if live behavior diverges from matrix.
