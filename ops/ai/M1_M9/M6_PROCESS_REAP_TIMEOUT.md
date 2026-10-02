# M6 — PROCESS_REAP_TIMEOUT (Muse 6)

Stand: 2026-09-28, Quelle: Voll-Read `scripts/windows_worker/daemon.py` (378 Zeilen)

## USER_PROBLEM (Operator-Sicht)
Ein Task laeuft in den Timeout — ist er dann tot? Oder laeuft er weiter, waehrend
Courier schon den naechsten Versuch startet (doppelte Wirkung)?

## CURRENT_RUNTIME_TRUTH (belegt)
- `run_task`: `Popen` + `communicate(timeout=600)`, blankes `except → FAILED`
  (`daemon.py:214-223`). KEIN kill/terminate/taskkill/wait im GESAMTEN File
  (vollstaendig gelesen, nicht gesucht). Der getimte-outete Kindprozess lebt weiter.
- Server-Retry: FAILED bei attempts<3 → QUEUED (`app.py:391-393`) → naechster Claim
  startet Ausfuehrung Nr. 2, waehrend Nr. 1 ggf. noch wirkt = Doppel-Effekt-Fenster
  OFFEN (Identitaet schuetzt nur das RESULT, siehe M4).
- `run_id` = nackte PID (`daemon.py:216`) — nach Exit wiederverwendbar, keine
  create_time-Bindung. Lock = msvcrt plain-PID ohne Leser im File.
- Worker-seitiges Task-Kill existiert NIRGENDS (nur Release-Pfade, M5).

## VERDIKT
M6-OPEN (HIGH, bestaetigt auf diesem SHA): Timeout ≠ Tod. Jeder Timeout ist als
EFFECT_AMBIGUOUS zu behandeln (gleiche Klasse wie Crash). Retry nach Timeout hat
doppelten-Effekt-Blast-Radius, bis der Daemon-Owner einen Kill-Tree liefert.
Kein Code-Eingriff von hier (Prep-only, fremde Lane).

## ACCEPTANCE_REQUIREMENT
M6.1: Timeout-Results tragen `EFFECT_AMBIGUOUS` sichtbar (nicht nur FAILED).
M6.2: Vor `resume retry` nach Timeout warnt das System: "Vorgaenger ggf. noch
  aktiv — Effekt pruefen, dann entscheiden." Stilles Retry ist verboten.
M6.3 (Owner, Code): Kill-Tree bei Timeout + PID+create_time-Bindung.

## MISSING_SYSTEM_SUPPORT
- Kein Kill, keine Effekt-Klassifizierung, keine Timeout-Warnung im Flow.

## PREPARABLE_NOW
- Dieses Paket + Warntext-Entwurf M6.2 + Eskalations-Notiz an Daemon-Owner.

## BLOCKED_UNTIL
- Daemon-Owner-Fix (M6.3) ODER dokumentierte Risiko-Akzeptanz VOR retry-lastigen
  Beweisen (M9-Eingang).

## NEXT
M7 (RUN1-Beweiskette) — M6 liefert: Timeout-Retry ist das groesste Effekt-Risiko.
