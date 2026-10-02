# POOL REPORT — WIN-004 FAILED_RETRY_MATRIX (DONE)

POOL_MISSION=COURIER_WINDOWS_MASTER_POOL_20260926 TASK=WIN-004
BY=WIN-06 SESSION=01a0dcac-1002-7e02-bb95-adacfb630c52 DATE=2026-09-26
MODE=READ_ONLY_ANALYSIS SHELL=DOWN. P3 + listed files READ ONLY (zero writes).

## Tree-mutation warning (affects all server/app.py evidence)
server/app.py SHRANK mid-session: an earlier direct read returned claim_task at
lines 723-812 (next_retry_at, provider locks, same-worker DISPATCHED reclaim);
a later read hit EOF at line 562 (`app.run`). Current dispatch lives at ~250-350.
Consequence: ANY app.py:560+ line refs (mine or peers') are STALE. Rows below
are grounded ONLY in current-tree reads (result 352-413, reclaim 416-454,
verify head 466-481, dispatch 280-347, claim head 271-275, intake 114-146,
daemon.py 1-403 full, watchdog.py:21-32) unless marked STALE.

## Matrix (SAFE / UNSAFE / UNKNOWN)

R1 delivery retry (identical result repost): SAFE.
- task_result ACK_DUPLICATE when stored matches (dispatch_id,result_id,status)
  (367-368); daemon reposts SAVED marker bytes then unlinks (daemon.py 112-117,
  380-382). Result never recomputed on repost.
- CAVEAT C1 (deferred, not duplicated): contradictory shape gets 409
  "Conflicting result..." (369-370) but daemon matches '"CONTRADICTORY_DUPLICATE"'
  (daemon.py 80-82) -> string mismatch -> 5x pointless retry + RuntimeError +
  loop-level re-attempt, marker stuck. OWNED BY live peer WIN-03 W4
  (error-contracts). No separate audit here.

R2 execution retry (FAILED result -> QUEUED while attempts<3): CONDITIONAL.
- SAFE iff task effect-free/idempotent; UNSAFE-IF-EFFECTFUL-NONIDEMPOTENT.
- Server re-queues on ANY non-SUCCESS result (388-390) with NO effect-proof
  gate: TimeoutExpired (daemon.py 199-201), missing artifact (214-227), even
  AMBIGUOUS_CRASH-FAILED all recycle to QUEUED. Fresh dispatch_id (uuid) +
  attempt_id per dispatch (329-331) -> daemon treats retry as NEW execution
  (same_execution keys, daemon.py 102-104) -> effect re-runs. Partial effects
  can double-apply. Owner call: effect-critical tasks need idempotency or
  human gate before retry (no fix by me; writer scope).

R3 new-attempt identity + terminal: SAFE.
- attempts init 0 (116,146), +1 per dispatch with uuid dispatch_id and
  `task:attempt:N` id (329-331); no cross-attempt confusion possible via
  same_execution keys. attempts>=3 -> FAILED_TERMINAL + goal BLOCKED
  (391-404): no auto re-dispatch past terminal.

R4 repeated side effect via stale/dead worker: SAFE (fail-closed).
- Watchdog loop POSTs /tasks/reclaim_stale (courier_watchdog.py:21-32).
- Server quarantines stale-owned (>300s unseen) DISPATCHED work to
  HUMAN_REQUIRED/STALE_WORKER_EFFECT_AMBIGUOUS (416-454); `reclaimed_tasks`
  is ALWAYS 0 — nothing auto-replays. Goal BLOCKED until human acts.
- Current dispatch (280-347) + claim head (271-275) contain NO auto-replay
  path (old-rev same-worker reclaim is STALE). Liveness cost accepted by design.
- Related peer coverage (cited, not redone): WIN-01 W3_leases,
  MUSE-45 T14_restart_recovery / WATCHDOG_reclaim / DISPATCHER_guards.

R5 STARTED-ambiguous (claim response lost / crash pre-result): SAFE.
- Worker re-claim -> WORKER_BUSY, task None (271-275): no double issue.
- Daemon crash with unknown effect -> AMBIGUOUS_CRASH FAILED post, never
  replayed (daemon.py 125-147). Ultimate backstop = R4 quarantine.

R6 RESULT_READY redelivery + verify->next: SAFE.
- ACK_DUPLICATE at result ingest (367-368) and at verify/reconcile keyed on
  result_id (478-480); SUCCESS waits independent /verify (385-386, 466+);
  verify idempotent per result_id. Redelivery cannot fork or double-count.

## UNKNOWNs (explicit)
U1 watchdog loop cadence + deployment wiring (sleep value / scheduler / who
runs watchdog in prod): not read here; see MUSE-45 WATCHDOG_reclaim (peer).
U2 old-rev-only behaviors (next_retry_at gate, provider locks/quota pools,
same-worker DISPATCHED reclaim): removed or relocated in restructure.
U3 concurrency beyond @serialize_state_mutation: assumed serialized, not audited.
U4 validate_durable_result required-field logic (prior MUSE longrun note):
writer-scope detail, not re-audited here.

## Verdict
Delivery retry SAFE; new-attempt identity SAFE; stale/ambiguous replays SAFE
by quarantine; verify idempotent. ONE conditional hole: R2 re-queues
effectful FAILED attempts without effect-proof — UNSAFE unless the task is
idempotent. Recommend owner rule: effect-critical tasks carry idempotency
proof or route to human gate before retry 2+. C1 (contract string mismatch)
with WIN-03 W4.

## Dedup / hygiene
No WIN-004 matrix existed (workspace search + peer frontier check). Adjacent
rows cite WIN-01 W3/MW1, MUSE-45 T14/WATCHDOG/DISPATCHER, WIN-03 W4, MW3 (S1/S3).
No foreign file touched. No commit possible (shell down).
FILES: runtime/slots/WIN-06/POOL_WIN-004_CLAIM.md (DONE), this report.
NEXT CANDIDATE: WIN-008 IDLE_COST (open, shell-less static) or WIN-001
P3_PATCH_AUDIT (docs/p3 present; writer-scope check first).
