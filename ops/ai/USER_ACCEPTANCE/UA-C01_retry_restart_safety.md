# UA-C01 — Failure/Retry/Restart: Darf ich es sicher erneut versuchen?

Prioritaet: C (Failure / Retry / Restart)
Stand: 2026-09-28, Quelle: Repo-Reads (kein RUN, kein Ledger, keine Revalidierung)

## USER_PROBLEM
Ein Task schlaegt fehl oder bleibt haengen. Als Nutzer weiss ich nicht: Darf ich
einfach Retry druecken? Wird die Aktion dann doppelt ausgefuehrt? Darf ich den
Worker neu starten, waehrend ein Task laeuft? Und wenn Retry verweigert wird —
warum, und was soll ich stattdessen tun? Heute gibt es keine nutzerlesbare
Antwort; die Sicherheitsregeln stehen nur im Code.

## CURRENT_RUNTIME_TRUTH (belegt)
- Retry ist NUR aus `HUMAN_REQUIRED` / `FAILED_VERIFICATION` / `FAILED_TERMINAL`
  erlaubt (`server/app.py:536-537`); aus `DISPATCHED`/`QUEUED`/`RESULT_RECEIVED`/
  `RECONCILED` antwortet der Server 400. `force_success` ist immer 400
  (`:551-554`): Erfolg kommt nur aus Ergebnis + unabhaengiger Verifikation.
- Kein Blind-Replay: Stale-Worker (>300 s, `server/app.py:425`) werden
  quarantiniert (`HUMAN_REQUIRED` + Goal BLOCKED, `:433-452`); `reclaimed_tasks`
  ist immer 0 (`:457`). Neustart mit Gedachtnisverlust -> Quarantaene, nie
  Replay (`:195-208`).
- Worker at-most-once: `CLAIMED -> STARTED -> RESULT_READY -> (RELEASE_PENDING)`
  (`scripts/windows_worker/daemon.py:137-149`); Crash in STARTED -> Freigabe an
  Recovery statt Re-Run (`:293-302`); 4xx vom Server -> `RELEASE_PENDING` +
  Freigabe (`:345-354`). Doppel-Send desselben Ergebnisses -> `ACK_DUPLICATE`,
  alles andere an verarbeiteten Tasks -> 409 (`server/app.py:364-373`).
- Auto-Retry: FAILED mit attempts<3 geht zurueck nach QUEUED (`:391-395`).
- Konkret heute: `task-replace-001` ist DISPATCHED
  (`server/state/central_state.json`) — ein Retry wuerde HEUTE mit 400
  abgewiesen, korrekt, aber ohne Nutzer-Erklaerung.
- Fehlend: keine Status->Aktion-Tabelle, kein "Warum wurde mein Retry
  abgelehnt"-Text, kein Restart-Runbook (Worker-Neustart waehrend DISPATCHED
  ist sicher per Design, steht aber nirgends fuer den Nutzer).

## ACCEPTANCE_REQUIREMENT
UA-C01.1: Zu jedem Task-Status gibt es genau eine Nutzer-Aktion:
  `QUEUED/DISPATCHED` = warten (Retry verboten, WENN es eilt: nichts tun, Watchdog
  entscheidet); `RESULT_RECEIVED` = Verifikation laeuft, warten;
  `HUMAN_REQUIRED/FAILED_*` = Retry erlaubt (ein Knopf, ein Endpoint);
  `RECONCILED` = fertig, kein Retry moeglich/noetig.
UA-C01.2: Jede Retry-Ablehnung nennt Grund + naechste Aktion in einem Satz
  (z.B. "Task laeuft noch bei Worker X — warten oder Worker-Status pruefen"),
  nie nur einen Code.
UA-C01.3: Worker-Neustart ist jederzeit als sicher dokumentiert (at-most-once,
  Quarantaene statt Doppel-Effekt); Server-Neustart ist sicher, aber nie zwei
  Server parallel (Single-Process-Lock).
UA-C01.4: `force_success` bleibt verboten; es gibt keinen manuellen
  "Als-erledigt-markieren"-Knopf — Erfolg braucht Ergebnis + Fremd-Verifikation.

## MISSING_SYSTEM_SUPPORT
- Kein nutzerlesbarer Fehler-/Aktions-Text im Server (nur HTTP-Codes + Englisch).
- Kein Endpoint/Feld, das "Retry erlaubt? Ja/Nein + Warum" beantwortet.
- Kein Restart-Runbook, keine Status->Aktion-Tabelle im Repo.

## PREPARABLE_NOW (ohne RUN, ohne Ledger)
- Dieses Dokument + Status->Aktion-Tabelle (Entwurf, s. UA-C01.1).
- Ablehnungs-Textbausteine (ein Satz pro Status, s. UA-C01.2).

## BLOCKED_UNTIL
- Echte Failure-Beobachtung (physischer RUN mit Timeout/Crash) fuer
  realistische Wortlaute — keine erfundenen Fehlermeldungen.
- Owner-Entscheid: Wo lebt spaeter der "Retry erlaubt?"-Check (Server-Feld
  vs. Shell-Logik)? Nur notiert, nicht gebaut.

## NEXT
UA-E01 (Progress/Next-Action-Anzeige).
