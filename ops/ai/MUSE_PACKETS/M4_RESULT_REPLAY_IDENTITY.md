# M4 — RESULT_REPLAY_IDENTITY (Muse 4)

Stand: 2026-09-28. Statische Kettenpruefung (Code gelesen, nicht ausgefuehrt).

## Identitaetskette (belegt)
1. Claim praegt frische IDs: `attempt_id = task:attempt:N` + `dispatch_id = uuid`
   (`server/app.py:323-325`), Task → DISPATCHED, Worker → busy.
2. Result bindet an Dispatch: `validate_durable_result` + `check_reference` fuer
   Upload-Refs (`app.py:374-380`); Fehler → 400.
3. Exakter Resend (verlorene Antwort) → `ACK_DUPLICATE`: Vergleich ueber 8 Felder
   (goal/task/attempt/dispatch/worker/run/result/status) + sortierte Artifacts
   (`app.py:361-367`).
4. Jeder ANDERE Result-Eingang auf verarbeitetem Task → 409 (`app.py:368-369`).
5. Resume-retry stellt QUEUED + worker=None (`app.py:545-548`); naechster Claim
   praegt NEUE attempt/dispatch-IDs, sodass alte Results nicht mehr binden
   (Kommentar `:542-544`, Mechanik `:323-325`).
6. Daemon-Seite: `current_task.json`-Phasen — STARTED nie re-rannen,
   RESULT_READY nur (re-)delivern, RELEASE_PENDING → freigeben
   (`windows_worker/daemon.py:153-158`, `mac_worker/daemon.py:70-76` + Release-Pfade).

## Statisches Urteil
- Kette ist KOHÄRENT GEZEICHNET: kein Pfad gefunden, der einen Doppeleffekt als
  Erfolg bestaetigt (4xx → REJECTED → RELEASE_PENDING → Quarantaene statt Replay).
- `force_success` ist beidseitig verriegelt (Result: kein Pfad; Resume: 400 mit
  "retry and verify instead", `app.py:554-557`).
- OFFEN (nur beobachtbar, nicht lesbar): ob zwei zeitgleiche Claims je doppelt
  DISPATCHED erzeugen koennen (Lock ist prozesslokal: `STATE_LOCK`, `app.py:47-53`;
  Mehrprozess-Betrieb waere ungeschuetzt — Deployment-Frage, kein Code-Urteil).

## ACCEPTANCE / REQUIREMENT
- M4.1: Replay-Regel in Nutzersprache (fuer UA-C01): "Gleiches Result erneut
  schicken = ACK, kein Doppeleffekt. Neues Result nach Verarbeitung = 409.
  Nach Resume gelten alte IDs nicht mehr."
- M4.2: Deployment-Regel: genau EIN Server-Prozess pro State-Datei
  (sonst ist M4-Offen ein Loch). Gehoert in Onboarding (UA-F01).
- M4.3: Beweis-Vormerkung (fuer Mac-RUN, nicht hier): Resend-Test
  (ACK_DUPLICATE) + Resume-Test (alte IDs binden nicht) als Pflichtfaelle.

## MISSING_SYSTEM_SUPPORT
- Kein sichtbarer Idempotenz-Status pro Task im `/status` (nur Zaehler).
- Kein Dokument "was passiert bei Doppel-Post" fuer Nutzer (→ UA-C01).

## BLOCKED_UNTIL
- Laufzeit-Beweis erst mit physischem RUN (ACK-Fall + Resume-Fall loggen).

## NEXT
M5 (Heartbeat/Restart — die Lease-Seite derselben Kette).
