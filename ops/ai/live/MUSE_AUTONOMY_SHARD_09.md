# Shard 09 — Stale Worker Takeover (READ_ONLY_C2, 0 edits, 0 runs)

SHARD=09
STATUS=COMPLETE (5 subcases, source-grounded, worktree HEAD bd539f18)
OWNER_SESSION=cloud-octans · DATE=2026-09-28
SUBCASES_DONE=5
CONFIRMED_SOURCE_DEFECTS=0
EVIDENCE_GAPS=1 (watchdog supervision: mechanism sound, operator-proof absent)
DISPROVEN=1 (heartbeat revives stopped worker — code forbids: unregistered sticky)
FIX_PACKETS=0
NEXT_OWNER=— (shard exhausted; operator note below)
DO_NOT_REPEAT=shard09-stale-takeover-5sub

## S1 Quarantine scope: NO_ISSUE + boundary
- `reclaim_stale` (app.py:442+) quarantines only DISPATCHED steps of stale
workers → HUMAN_REQUIRED + STALE_WORKER_EFFECT_AMBIGUOUS, goal stays ACTIVE
(not BLOCKED here — contrast heartbeat-divergence path which BLOCKs).
- RESULT_RECEIVED tasks of dead workers NOT quarantined: correct — result
persists for independent verify. Boundary recorded.

## S2 Pre-reclaim window: NO_ISSUE (no duplicate dispatch)
- Claim serves only QUEUED at current_step_index (app.py:299-305); a
DISPATCHED task of a disappeared worker is un-claimable until reclaim.
Effect: stall (≤60s w/ watchdog), never duplicate execution.

## S3 Reclaim trigger: NO_ISSUE (mechanism) + EVIDENCE_GAP (supervision)
- `courier_watchdog.py run_loop`: POSTs /tasks/reclaim_stale every 60s,
logs quarantined counts. Automated, not manual-only.
- Gap: no in-repo proof the watchdog itself is supervised (if watchdog dead,
stall is indefinite). Operator-owned (supervisor config), not code defect.

## S4 Liveness clock: NO_ISSUE (consistent 300s)
- `last_seen` stamped by heartbeat (:270), claim (:288), register;
stale=300s in reclaim (:445) AND cost-routing skip (:322). Single threshold,
no drift. Heartbeat of unknown worker → 404 (stays stopped).

## S5 Sticky stop: risk DISPROVEN
- unregister sets available=False + unregistered=True (:257-259); heartbeat
restores available ONLY if not unregistered (:273-274). Only explicit
re-registration returns worker to service. No revival path.
