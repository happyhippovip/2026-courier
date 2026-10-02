# MUSE-45 T-H — Queue/auto-next coverage map (read-only)

MISSION=COURIER_LIVE_SHOW_CONTINUE, slot MUSE-45, date 2026-09-26.
Method: static tree evidence only (shell DOWN). Nothing modified but this packet.

## Implementation locus (OBSERVED)

- `replenish|REPLENISH` in prod code matches ONLY `server/app.py` (P3 read-only).
  No replenishment logic in scripts/. Auto-next/replenish is server-owned;
  read-only observation, no edit possible or attempted.

## Test shape (OBSERVED, not run)

- tests/test_auto_replenishment.py is a LIVE integration test: module fixture
  starts real `server.app` + `scripts/courier_verifier.py` as subprocesses on
  port 8081 (COURIER_MOCK_CHIEF=1), tears them down with terminate/kill.
- Hygiene notes (not defects, cannot run to confirm impact):
  - fixture deletes `~/.courier_runtime/server/state/central_state.json`: the
    test mutates user-home runtime state, so parallel/overlapping runs (or a
    live local server using the same home state dir) collide. Owner may want an
    isolated state path.
  - fixture carries hardcoded test API keys (localhost test-only). Same class
    as the earlier hardcoded test-key finding; quoted nowhere here.
  - port 8081 fixed: parallel live-test runs collide. Owner call.

## Verdict

Auto-replenishment HAS a live test path; it is unrunnable from here (shell DOWN)
and its isolation hygiene is owner-reviewable. Queue/auto-next fallback item
covered to the static limit.
