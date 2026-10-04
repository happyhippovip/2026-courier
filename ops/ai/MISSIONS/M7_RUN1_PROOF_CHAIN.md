# M7 — RUN1_PROOF_CHAIN (Muse 7)

Stand: 2026-09-28. Prep-only: kein RUN, nur Ketten-Spec pruefen.

## OBJECTIVE
Die RUN_1-Beweiskette auf Luecken pruefen, BEVOR sie laeuft: Ist jede
Behauptung (genau-einmal, Hash, Server-Bytes, RECONCILED) einer konkreten
Evidenz-Datei zugeordnet, und passt der Pruefer zum echten Format?

## ANCHORS (belegt, eigene Reads)
- Layout: `artifacts/run1/` (ledger db, 3 Logs, A.proof, A-Status, bindings)
  (`MAC_RUN_1_EVIDENCE_LAYOUT.md:6-15`); 4 Behauptungen GQ15–GQ18 + Synthese.
- Command-Sheet: Branch `coordination/mac-handoff-20260928`,
  `run_1_mac.sh`, Prozess-Checks (`MAC_RUN_1_COMMAND_SHEET.md`).
- Bekannte Format-Luecke (UA-D01): `verify_run1_evidence.py` erwartet SQLite,
  Server schreibt JSON (`app.py:11`).

## SCOPE (read-only)
RUN_1-Sheets + Layout, `scripts/mac_worker/run_1_mac.sh`,
`verify_run1_evidence.py`, `server/app.py` (State-Format).

## METHOD
Statisch: jede GQ15–GQ18-Behauptung -> Evidenz-Datei -> Pruef-Schritt
verbinden; Brueche markieren (Datei fehlt im Layout, Pruefer passt nicht,
Branch/Skript existiert nicht). NICHTS ausfuehren.

## OUTPUT
Ketten-Tabelle `BEHAUPTUNG | EVIDENZ_DATEI | PRUEFER | BRUCH?`.
Verdict: `RUN1_CHAIN_COMPLETE_STATIC: YES|NO` + Bruch-Liste nach Schwere.

## BLOCKED_UNTIL
Mac RUN_1 (fremder Runner) — diese Mission bereitet nur vor.

## DONE_WHEN
Alle 4 Behauptungen + Synthese sind verkettet; jeder Bruch hat eine Zeile.
