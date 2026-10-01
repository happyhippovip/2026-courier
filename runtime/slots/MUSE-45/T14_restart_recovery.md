# T14 RESULT — Restart/Recovery paths (static, read-only)

MODE: shell-less LIGHT. Server paths in server/app.py (P3, read-only);
worker paths in scripts/windows_worker + scripts/mac_worker. No execution.

## Server side (canonical state)
- STATE_FILE=server/state/central_state.json (COURIER_STATE_FILE override).
  save: tmp-per-thread + flush + fsync + os.replace, 20x PermissionError retry.
  load: 20x retry (PermissionError/IOError/JSONDecode), schema 1->2 migrate,
  fail-closed sys.exit(1) on future schema. (app.py:440-492)
- POST /tasks/reclaim_stale (987): workers unseen >300s -> unavailable;
  their DISPATCHED steps -> HUMAN_REQUIRED/STALE_WORKER_EFFECT_AMBIGUOUS
  (NO auto-replay: "may already have produced an effect"). Goal BLOCKED.
  Returns reclaimed_tasks:0 — honest, quarantines only.
- POST /tasks/<id>/resume (1261): only from HUMAN_REQUIRED/FAILED_*/
  WAITING_PROVIDER/BLOCKED_TRANSIENT. Transport wait (WAITING_PROVIDER/
  BLOCKED_TRANSIENT) resumes SAME attempt (transport retries bounded);
  HUMAN/FAILED re-executes as QUEUED with NEW attempt identity via claim.
- Checkpoint fields on every transition: last_completed_step, next_action,
  blocker, artifact_refs, retry_state, next_retry_at (T12).

## Worker side (durable markers)
- Windows daemon: effect_marker.json + result_marker.json in
  scripts/windows_worker/state/, atomic-written (tmp+fsync+replace).
  recover_pending_markers() at startup: unsent result -> resend SAME
  result_id (server dedupes via ACK_DUPLICATE, T12); ambiguous effect ->
  FAILED/AMBIGUOUS_CRASH which the server quarantines to HUMAN_REQUIRED.
  Same-execution identity over goal/task/attempt/dispatch/execution_ref.
- Mac daemon: state/current_task.json checkpoint + health_check reporter.

## Findings
R-T14-1 (OK) CRASH CHAIN IS COHERENT END-TO-END (statically).
marker -> AMBIGUOUS_CRASH -> HUMAN_REQUIRED quarantine; result resend is
idempotent by result_id; no path silently drops or double-applies an
effect. This is the crash-boundary design the RC acceptance run needs —
still requires the live crash test as proof (structure != proof).

R-T14-2 (LOW) STATE TMP NAME LACKS PID.
save_state tmp = STATE_FILE.<threadident>.tmp (app.py:480). Two server
PROCESSES (cf. T8 double-bind: motor flask + waitress) could collide on
the tmp name. Narrow (usually prevented by the :8080 conflict), but the
state file is shared even if ports differ. Fix direction: include PID.
Owner: server scope.

R-T14-3 (INFO) reclaim_stale NAME OVER-PROMISES.
It never reclaims (returns 0 by design); it quarantines. Behavior is the
safe choice; name suggests otherwise. Cosmetic.

R-T14-4 (OK) RESUME IDENTITY HYGIENE SOUND.
Transport-retry preserves attempt; re-execution mints new identity via
claim; unresumable statuses rejected 400. OK.

## Disposition
Read-only mission: NO FIXES. R-T14-2 handed to server owner.
No files outside runtime/slots/MUSE-45 touched.
