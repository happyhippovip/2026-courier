# M5 — WORKER_HEARTBEAT_RESTART (Muse 5)

Stand: 2026-09-28. Prep-only: statische Analyse, kein RUN, kein Ledger.

## OBJECTIVE
Heartbeat-/Restart-Semantik aus Nutzersicht klaeren: Wann gilt ein Worker als
tot, was passiert mit seinem Task, und was sieht der Nutzer davon?

## ANCHORS (belegt, eigene Reads)
- Stale-Schwelle 300 s (`server/app.py:425`); Watchdog ruft `reclaim_stale`
  alle 60 s (`courier_watchdog.py:27,39`).
- Stale + DISPATCHED -> `HUMAN_REQUIRED` + Goal BLOCKED (`app.py:436-452`).
- Register mit abweichendem `current_task` -> Quarantaene (`:195-208`);
  ohne Feld -> Server-Task bleibt (`:209-210`).
- Unregister ist sticky, nur Re-Register heilt (`:225-239`).
- Bekannt: 600-s-Task-Block vs. 300-s-Stale = Quarantaene mitten im Lauf.

## SCOPE (read-only)
`server/app.py` (register/heartbeat/reclaim), `courier_watchdog.py`,
beide Daemons (Heartbeat-Stellen), `central_state.json` (Beispiel-Worker).

## METHOD
Statisch: Zeitdiagramm der Faelle (gesund/still/crash-vor-persist/restart-mit-
amnesie) zeichnen; je Fall Server-Urteil + Nutzer-Sichtbarkeit ableiten;
Luecke "Worker stirbt, Nutzer merkt nichts bis Quarantaene" bewerten.

## OUTPUT
Fall-Tabelle `FALL | SERVER_URTEIL | NUTZER_SIEHT | ZEIT_BIS_SICHTBAR`.
Verdict: `RESTART_SEMANTICS_CLEAR: YES|NO` + schmerzhafteste Luecke zuerst.

## BLOCKED_UNTIL
Echte Heartbeat-Logs aus physischem RUN fuer Zeit-Belege.

## DONE_WHEN
Alle fuenf Faelle sind tabelliert; kein Fall ohne Nutzer-Sichtbarkeits-Zeile.
