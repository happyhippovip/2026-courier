# WATCHDOG/RECLAIM NOTE — quarantine-only, acceptance-path impact (static)

Files: scripts/courier_watchdog.py, server/app.py:990-1025. Read-only.

## W-1 (MEDIUM) "Reclaim" never reclaims — it quarantines and BLOCKS the goal
- POST /tasks/reclaim_stale ALWAYS returns {"reclaimed_tasks": 0, ...}
  (hardcoded app.py:1025). The watchdog's "Reclaimed N tasks" log line is
  dead code in practice.
- Real behavior: DISPATCHED steps owned by workers silent >300s go to
  HUMAN_REQUIRED/STALE_WORKER_EFFECT_AMBIGUOUS, and the whole goal flips to
  BLOCKED (app.py:1007-1020).
- Acceptance impact (RC: USER_CONTINUE_MESSAGES=0, CLEAN_IDLE required): ONE
  worker silence >300s (crash, network stall, machine sleep) during the
  physical run permanently BLOCKS the goal — no auto re-dispatch exists.
  The run cannot self-heal; it needs a human or a fresh goal. Owner to
  decide: (a) accept as fail-closed design + require 2+ live workers with
  heartbeats << 300s during proof, or (b) add true re-dispatch for
  effect-proven-unstarted tasks. Design decision, NOT my call.
- Naming: endpoint + logs say "reclaim"; behavior is "quarantine". Rename or
  document to prevent the next reader assuming self-healing (this session's
  G-4 note assumed a re-dispatch net — corrected here: the net is
  quarantine-to-human, not recovery).

## Corroborated GOOD
- Thresholds consistent: 300s server-side and watchdog comment; 60s poll.
- Ambiguity handling is principled: DISPATCHED-may-have-effects is never
  silently replayed (duplicate-effect prevention prioritized over liveness).
- Worker record cleanup (current_task=None, available=False) is coherent.

## Suggested test pin (owner, needs shell)
Reclaim endpoint test exists? Not checked this pass — suggest asserting the
quarantine-only contract (reclaimed==0 always, HUMAN_REQUIRED set, goal
BLOCKED) so the behavior is pinned whichever design is chosen.
