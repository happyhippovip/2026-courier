# M6 — PROCESS_REAP_TIMEOUT (Muse 6)

Stand: 2026-09-28. Prep-only: statische Analyse, kein RUN, kein Ledger.

## OBJECTIVE
Timeout-/Aufraeum-Verhalten des Workers bestimmen: Was passiert mit dem
Kind-Prozess bei 600-s-Timeout, wer raeumt auf, und kann ein verwaister
Prozess spaeter doppelt wirken?

## ANCHORS (belegt, eigene Reads)
- `run_task`: `communicate(timeout=600)`, nacktes `except Exception -> FAILED`
  (`scripts/windows_worker/daemon.py:214-224`); KEIN kill/terminate/taskkill
  in der gesamten Datei (Voll-Read).
- Bei Timeout lebt das Kind weiter; Server-Retry = Doppel-Wirkungs-Fenster.
- Lock: `msvcrt LK_NBLCK`, Plain-PID ohne Leser (`:252-264`).
- `stop.bat`: ungezieltes `taskkill /F /IM python.exe` + Titel-Filter.

## SCOPE (read-only)
`scripts/windows_worker/daemon.py` (voll), `stop.bat`/`start.bat`,
Mac-Daemon zum Vergleich (nur Timeout-/Kill-Stellen).

## METHOD
Statisch: Timeout-Pfad Schritt fuer Schritt verfolgen (wer stirbt, wer lebt,
wer meldet was); verwaiste-Prozess-Szenarien aufzahlen; `stop.bat`-Risiko
(Fremd-Prozess mit passendem Titel) einschaetzen. Keine Prozesse starten.

## OUTPUT
`TIMEOUT_KILLS_CHILD: YES|NO` (belegt) + Szenarien-Tabelle
`SZENARIO | FOLGE | NUTZER_RISIKO` + minimaler Fix-Vorschlag (Text, kein Code).

## BLOCKED_UNTIL
Physischer Timeout-Test (fremder RUN) fuer Laufzeit-Bestaetigung.

## DONE_WHEN
Timeout-Pfad ist vollstaendig beschrieben; Fix-Vorschlag ist ein Absatz,
kein Patch.
