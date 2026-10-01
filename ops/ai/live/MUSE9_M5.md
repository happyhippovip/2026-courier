# MUSE9 M5 — unregister/heartbeat/restart/stale (Sidecar, READ_ONLY_C2)

Kein RUN, keine Revalidierung.

## Reuse zuerst
- `ops/ai/M1_M9/M5_WORKER_HEARTBEAT_RESTART.md`.
- `server/app.py:195-202,419-458`; `windows daemon.py:317-338,393`; `courier_watchdog.py:27-39`.

## Subcases
- M5-S1 Heartbeat/Stale-Zahlen: Daemon-Heartbeat am Schleifenkopf (`:330-338`), Sleep 10 s am Schleifenende (`:393`); Server stale nach 300 s (`app.py:425`); Watchdog tickt 60 s. VERDIKT: CONFIRMED (Code, Refute-Stand).
- M5-S2 Reclaim: DISPATCHED-auf-stale → HUMAN_REQUIRED + BLOCKED
  (EFFECT_AMBIGUOUS); `reclaimed` hart 0 — nie Blind-Replay.
  VERDIKT: CONFIRMED (Code).
- M5-S3 Unregister sticky: nur explizites Re-Register bringt zurueck (`app.py:220-234`, Refute-Stand).
  VERDIKT: CONFIRMED (Code).
- M5-S4 Restart-Pfade: `register(current_task=None)` → Quarantaene
  (WORKER_RESTARTED…, `app.py:195-202`); Daemon-STARTED-Crash → Release ohne Re-Execute
  (`windows daemon.py:317-328`, Refute-Stand).
  VERDIKT: CONFIRMED (Code).
- M5-S5 Live-Stale: `task-replace-001` haengt DISPATCHED an totem Worker
  (`NEW-WIN-PC-01`, last_seen ~11 Tage). Ausgang (Quarantaene) unbeobachtet —
  kein Server gesehen. Follow-up-Probe: Fall UNVERAENDERT (gleicher dispatch/worker/attempt);
  State aber um +2 Test-Goals gewachsen (`goal-51043ae8`, `goal-5409572b`, beide ACTIVE,
  "do something"/"test-worker", Steps RESULT_RECEIVED) → Test-Pollution des Live-States.
  VERDIKT: CONFIRMED (State); MISSING_EVIDENCE (Ausgang).
- M5-S6 Lease-Loch 600 (`windows daemon.py:239`)>300 (`app.py:425`, Refute-Stand): gesunder Lang-Task wuerde mid-run quarantiniert
  (danach idempotent 409→Release, kein Wedge). MEDIUM.
  VERDIKT: CONFIRMED (Mechanismus).

## OUTPUT
ROLE=M5
CONFIRMED=M5-S1/S2/S3/S4 (Mechanik); M5-S5-State (lebender Stale-Fall); M5-S6 (Lease-Loch)
DISPROVEN="Blind-Replay nach Restart"; "Automatisches Wiederanlaufen"; "Unregister kehrt via Heartbeat zurueck"
MISSING_EVIDENCE=Quarantaene-Ausgang von task-replace-001 (braucht laufenden Server+Watchdog)
OWNER_PACKET=Stale-Indikator + Quarantaene-Grund ins UX-Vokabular (Spec: UA-C01.4/M5.1)
CRITICAL_PATH=M5-S5 → M9 BEFORE_RUN1 (lebender Stale-Fall als erster Quarantaene-Zeuge)
NEXT_OWNER=Server/UX-Owner (Indikator); RUN-Lane (Ausgangs-Beobachtung)
DO_NOT_REPEAT=Quarantaene als Bug umdeuten (ist Design); Watchdog-Intervall-Theorie ohne Messung
STATUS=DONE_STATIC

## FOLLOW_UP (2026-09-28, Selbst-Widerlegung)
ROLE=M5
SURVIVING_CONFIRMED=M5-S1/S2/S3/S4 (Mechanik); M5-S5 (Fall stabil); M5-S6
REMOVED=Nichts
MINIMUM_NEXT_ACTION=Test-Pollution stoppen: Tests duerfen Live-State nicht schreiben (→ M9-7); Quarantaene-Ausgang weiter offen
MINIMUM_TEST_OR_EVIDENCE=Watchdog-Tick auf laufendem Server (RUN-Lane)
NEXT_OWNER=Test-Owner (Isolation); RUN-Lane (Beobachtung)
STATUS=DONE_STATIC
