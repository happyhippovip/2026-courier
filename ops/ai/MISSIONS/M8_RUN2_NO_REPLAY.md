# M8 — RUN2_NO_REPLAY (Muse 8)

Stand: 2026-09-28. Prep-only: kein RUN, nur No-Replay-Spec pruefen.

## OBJECTIVE
Die RUN_2-Kernbehauptung absichern: Nach `kill -9` + Neustart darf Task A
(RECONCILED) NIE wieder dispatched werden, Task B muss automatisch starten.
Ist die Pruefung dafuer wasserdicht spezifiziert?

## ANCHORS (belegt, eigene Reads)
- RUN_2: `kill -9`, Port-Wait, Neustart, B-Bindung
  (`MAC_RUN_2_COMMAND_SHEET.md:10-14`); KRITISCH: A nie wieder dispatchen,
  B muss starten (`:16-18`); B-Verifikation (`:21`).
- Code-Seite: RECONCILED-Tasks werden nie erneut vergeben (Index-Gate,
  `app.py:277-280`); Amnesie -> Quarantaene statt Replay (`:195-208`).
- Abhaengigkeit: RUN_1 muss RECONCILED fuer A geliefert haben.

## SCOPE (read-only)
RUN_2-Sheet, `scripts/mac_worker/run_2_mac.sh`, `server/app.py`
(Claim-Gate, Register-Recovery), Freeze-Matrix RUN2-Zeilen.

## METHOD
Statisch: No-Replay-Beweis fuehren (welche Code-Stelle verhindert A-Redispatch
in jedem Crash-Zeitpunkt?); Pruef-Schritte des Sheets auf Vollstaendigkeit
pruefen (welcher Log beweist "A wurde NICHT dispatched" — Negativ-Beweis!);
Race-Fenster (kill waehrend Claim/Result/Verify) aufzahlen.

## OUTPUT
`NO_REPLAY_PROVEN_STATIC: YES|NO|PARTIAL` + Negativ-Beweis-Wuerdigung
(Grep-Abwesenheit = schwach, DB-Dump = stark) + Race-Tabelle.

## BLOCKED_UNTIL
Mac RUN_1 (Voraussetzung) + RUN_2 (fremder Runner).

## DONE_WHEN
A-Redispatch ist fuer jeden Crash-Zeitpunkt beantwortet; der Negativ-Beweis
ist als stark/schwach eingestuft.
