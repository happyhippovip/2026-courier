# MUSE AUTONOMY SHARD 08 — Heartbeat Truthfulness

SHARD=08
STATUS=SHARD_COMPLETE (5 subcases, all DISPROVEN, 0 defects, 0 gaps)
CLAIM.c2=elm-triton / HOST=MAC / 2026-09-28
MODE=READ_ONLY_C2, 0 source edits, 0 runs, 0 ledger. CODEX_HIGH_RESULT_CURRENT.md
absent → autonomy shards continue (phase check this run).

REUSE_EVIDENCE=muse-whats-left-L-01 (unknown-worker → 404 no-write;
unregistered respected by heartbeat).

## Subcases (source-grounded)
- S1 schema: worker record has exactly worker_id/platform/capabilities/
  last_seen/available/current_task/cost_class (server/app.py:233-241) — NO
  progress/result/activity/output field exists; heartbeat payload is worker_id
  only; server writes last_seen + conditional available (:270-277).
  → DISPROVEN (no channel for false progress/result claims exists).
- S2 busy-availability: available=True only if no current_task AND not
  unregistered (:274-276). Both daemons beat DURING execution (win thread
  scripts/windows_worker/daemon.py:219-230; mac loop
  scripts/mac_worker/daemon.py:369-376) yet server keeps available=False.
  → DISPROVEN (false-availability impossible via heartbeat).
- S3 quarantine-scope: heartbeat mutates ONLY the worker record (:270-277),
  never tasks/goals/result. Stale quarantine (tasks HUMAN_REQUIRED + goal
  BLOCKED, :~452-464) cannot be lifted by heartbeat; a revived worker only
  regains availability after proving liveness, old task stays quarantined.
  → DISPROVEN (false-recovery impossible via heartbeat).
- S4 beats-during-execution: win hb thread lives for the whole run (:219-230,
  stopped after communicate :232-235, timeout 600s); mac beats inside the
  exec loop (:373-376, deadline up to 3600s :368). "Silent during long tasks"
  → DISPROVEN both platforms.
- S5 interval margin (deterministic, no run): 30s beat (win :221, mac :369/:376)
  vs 300s stale threshold (:449) and 300s cost-routing ignore (:324) = 10
  consecutive missed beats required for false-stale. Residual note (not a gap
  claim): transport blackout >300s during execution fails safe toward stale
  quarantine (deliberate ambiguity rule :~454-456); win send-exceptions swallowed
  (:226-227), mac marks registered=False on hb failure (:482-487). Neither
  direction fabricates activity.

SUBCASES_DONE=S1,S2,S3,S4,S5 (+1 REUSE)
CONFIRMED_SOURCE_DEFECTS=(none)
EVIDENCE_GAPS=(none)
DISPROVEN=S1,S2,S3,S4,S5 (heartbeat content-truthfulness, 5 angles)
FIX_PACKETS=(none)
NEXT_OWNER=(none — nothing to own)
DO_NOT_REPEAT=muse-autonomy-shard-08-01
