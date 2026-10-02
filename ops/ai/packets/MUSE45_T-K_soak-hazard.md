# MUSE-45 T-K — Soak-test live-state hazard + G1 confirmation (read-only)

MISSION=COURIER_LIVE_SHOW_CONTINUE, slot MUSE-45, date 2026-09-26.
Method: static tree evidence only (shell DOWN). Nothing modified but this packet.

## H1 MEDIUM — soak_test.py would overwrite foreign DONE states on the live wall

- `scripts/windows_muse_wall/soak_test.py` runs against the REAL repo root
  (`root = Path(__file__).parent.parent.parent`, no tmp guard, no --root flag):
  start_slot(MUSE-01..03, sleep-10) -> stop MUSE-02 -> re-init -> reconcile ->
  stop rest.
- `supervisor.start_slot` (:172-198) sets `slot["state"] = "IDLE"` unconditionally
  on start; `stop_slot` (:200-220) sets READY. Running the soak on the live wall
  would therefore overwrite the DONE proof states of MUSE-01..03 (Google's
  staged-scaling evidence) and spawn real processes into foreign slots.
- initialize() itself is NON-destructive (:142-150, only creates missing
  state.json) — that half of the worry is disproved; the hazard is start/stop.
- reconcile (:162-170) correctly preserves DONE/BLOCKED on dead processes.
- Owner fix direction: tmp-root guard or explicit live-confirm + slot allowlist.
  Not fixed by me (Google-active scope, needs shell to test). Nobody has run it
  against live state as far as tree evidence shows (DONE states intact).

## Correction discipline

- Initial worry "initialize() resets live state" was disproved by reading
  :142-150 (exists-guard). Only the start/stop half stands, as H1 above.

## G1 (from T-D) CONFIRMED by scope rule-out

- No test references TIMEOUT_HUNG_TASK/abandon; both "hung" candidates ruled out:
  test_attestation_cross_defect_crash imports ledger only (no motor drain),
  test_queue_independent's "hung" is a daemon-run timeout message. The
  courier_continue 8s hang-abandon has zero test coverage in tree. (T-D updated.)
