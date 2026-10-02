# POOL MAINT — MW2_RETRY_RESTART_SAFETY matrix maintenance 01

BY=WIN-06 SESSION=01a0dcac-1002-7e02-bb95-adacfb630c52 DATE=2026-09-26
MODE=READ_ONLY SHELL=DOWN. Existing code/tests/reports consumed first; only
gaps/contradictions filed. No architecture, no fixes (writer scope).

## Revision context (read this first)
The tree churned mid-session under the active writer: server/app.py 1400+ -> 562
lines; scripts/windows_worker/daemon.py rewritten (old 403-line marker design ->
new phase-machine design, still evolving: MW1 refs drift ~6 lines vs current);
scripts/windows_muse_wall/*.py absent (2-witnessed: me + WIN-01 MW1);
stop_safe.py DELETED. All daemon/app line refs below are CURRENT (re-read this
turn); older refs are marked STALE-READ. All agents: timestamp + re-verify
server/worker evidence; file hashes when shell returns.

## Factual matrix (7 MW2 cases, current-tree grounded)

1. identical duplicate result: SAFE. Server ACK_DUPLICATE on
   (dispatch_id,result_id,status) (app.py:367-368, current). Daemon redelivers
   the persisted payload (phase RESULT_READY, UNDELIVERED-keep, daemon.py:350-355
   current). Old marker-mechanism refs (my RESULT_01/WIN-004) STALE-READ.
2. conflicting duplicate result: SAFE-FAIL-CLOSED. C1-original (409 string
   mismatch) is MOOT — old post fn removed. Current: 4xx -> REJECTED ->
   RELEASE_PENDING -> release to server recovery (daemon.py:113-135, 356-365);
   bounded attempts, no infinite retry. X6-LOW: docstring says "200 IGNORED",
   server sends ACK_DUPLICATE — cosmetic (code doesn't branch on body).
3. stale attempt: SAFE. Watchdog 60s poll (peer MUSE-45 WATCHDOG_reclaim) ->
   reclaim_stale quarantines >300s-unseen DISPATCHED to HUMAN_REQUIRED
   (app.py:416-454 current, reclaimed always 0). Daemon lock now msvcrt
   LK_NBLCK, self-releasing on death (daemon.py:263-275) — my F2 (plain-PID)
   MOOT for acquire.
4. RESULT_READY redelivery: SAFE. Keep + repost until DELIVERED (354-355);
   server + verify ACK_DUPLICATE (367-368, 478-479). Never recomputed.
5. STARTED ambiguity: SAFE. Restart normalizes unknown phases to STARTED and
   RELEASES to server recovery, never replays (daemon.py:298-313); server
   quarantine is the backstop (R3).
6. FAILED requeue side effects: CONDITIONAL-OPEN (unresolved, owner).
   Server re-queues ANY non-SUCCESS result while attempts<3 (388-390), incl.
   TimeoutExpired/partial-effect, with fresh dispatch_id+attempt_id (329-331)
   forcing re-execution. UNSAFE unless task idempotent. Recommended owner rule:
   effect-critical tasks need idempotency proof or human gate before retry 2+.
7. restart recovery: DESIGN-SAFE, refs-partially-stale. Phase machine +
   atomic persist_task tmp/fsync/replace (137-149) + release-on-ambiguity is
   sound. MW3 fixtures remain VALID SPECS; their daemon-mechanism refs are
   STALE (markers->phases, stop_safe deleted). Supervisor row still BLOCKED
   (wall *.py absent).

## Contradictions / gaps found (new this turn)
- X1 MW1-D1 "no kill/terminate/wait anywhere" vs current taskkill /F /T in
  TimeoutExpired + generic handlers (daemon.py:225,232). MW1 premise
  contradicted by current code (writer added kills after MW1's read, or
  search-miss — search false-negatives are proven). Flag for WIN-01/owner.
- X2 MW1-D4 "tasklist-substring stale check (248-269)" vs current msvcrt
  locking (263-275). Contradicted; >=2 daemon revisions today.
- X3 MUSE-45 WATCHDOG_reclaim app.py:990-1025 refs vs current 562-line file
  (reclaim now 416-454). Behavior consistent, refs stale.
- X4 test_windows_daemon_completeness vs current daemon API: persist_marker/
  same_execution/recover_pending_markers REMOVED (top-import -> module ERROR);
  is_resource_pressure_high signature/semantics changed (config arg, SIMULATE_*,
  mem check gone); acquire_lock semantics changed. Suite RED on current tree
  (static conclusion; runner must confirm). Checkpoint "65/65" stale.
- X5 my RESULT_01 / WIN-004 / MW3 daemon line refs -> STALE-READ (old
  403-line version). Verdicts re-grounded in this note.
- X6 stop_safe.py DELETED; stop.bat CONFIRMED broad-kill (taskkill /F /T
  /IM python.exe + WINDOWTITLE filter, stop.bat:3, direct read). Exact-STOP
  capability REGRESSED -> violates exact-process ownership. NEW UNSAFE,
  owner fix (writer scope). Wiring/scope per peers MUSE-45 T8, WIN-03/04 T7
  (cited, not re-audited). Daemon has no STOP handling (__main__ catches
  only MissingCredentialError, 384-389); killed daemon restarts into
  STARTED->release->quarantine (safe direction, availability cost).
- X7 worker_status marker/queue checks vs current daemon (phase file
  current_task.json; no markers; no queue.db writer): INFERRED stale
  (always-None branches). Not re-probed; pointer for runner session.
- U1 (watchdog cadence) RESOLVED via peer (60s). S2/supervisor still BLOCKED.

## Disposition: IDLE_SAFE (with resume triggers)
All 7 cases carry current verdicts. Remaining opens need shell (X4 confirm),
tree settle (S2, X7), or writer grant (X6 fix, R6 rule) — none actionable
read-only. Fresh pool tasks (WIN-008/WIN-001) would ground on churning code
(high instant-stale risk) -> not started per NO_BUSYWORK. NEXT-DECLARED (not
claimed, no squat): WIN-008 IDLE_COST, then WIN-001 P3_PATCH_AUDIT, when tree
settles + shell or writer-scope available. Resume triggers: shell back,
wall *.py restored, writer grant, or new peer evidence contradicting rows 1-7.
Consumed (cited, not duplicated): MUSE-45 WATCHDOG_reclaim/T-G/T-A/T8,
WIN-01 MW1/W3, WIN-03 W4/W5 (W4 = motor/ledger scope, not daemon-409 scope),
WIN-04 T6/T7, WIN-05 census, peer WIN-02 W02-01/W02-02. Zero foreign writes.
