# O7-12 · B6 · finish_turn ohne Canary gilt als fertig · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-12_test_finish_without_proof.py` · sha256 `c3b443ee4074f70e1322e972d2319012b5e24c124291ab37717bc1fdab6ebec8` |
| Marker | 1 × `xfail(strict=True, raises=AssertionError)` + 1 Schutztest |
| Lauf auf Basis | `1 passed, 1 xfailed`, Exit 0; mit `--runxfail`: `Workkey(key='WK-1', state='DONE', …, checkpoint='provider says done')` + DONE-Receipt |
| Kosten | 0 €, In-Process-Controller in tmp, kein Provider |

## Befund (VERIFIED)
- **Katalog-Input `scripts/automation_wake_coalescing.py`: nicht gefunden.** Dort gibt es weder `finish_turn` noch eine Canary-/Proof-Logik.
- **Schutz vorhanden (passed):** `LedgerEngine.finish_turn` (`courier_runtime/ledger_engine.py:228-252`) gibt ohne `journal:<seq>:RESULT_ACCEPTED` (`proof()`, `:216-226`) `NOT_PROVEN` zurück.
- **Echter Defekt (P1):** Der Signalpfad des Providers umgeht diesen Schutz. Eine Zeile `TURN_ENDED outcome=DONE` in der Signaldatei läuft so durch:
  1. `courier_runtime/host_loop.py:68-75` (`run_once`)
  2. `courier_runtime/provider_events.py:76-83` (`handle`)
  3. `courier_runtime/continuity.py:225-230` (`Kirby.on_turn_end(…, "DONE")`)

  Dort wird der Workkey auf **DONE** gesetzt und ein DONE-Receipt geschrieben, **ohne jeden Journal-Beweis**. Das widerspricht dem eigenen Satz in `finish_turn`: „DONE only with journal proof; the result decides, not the provider“.
- **Produktiv verdrahtet:** `courier_runtime/host_loop.py:141-156` (`main`) ruft `run_once(kirby, args.slot, args.signals, state)` mit genau dieser Signaldatei auf.

## Erwartung nach dem Fix
`outcome=DONE` aus Provider-Signalen wird höchstens zu `STILL_OPEN`/Reconcile; DONE gibt es nur über `finish_turn` mit Proof (oder Kirby verlangt den Proof-String in `on_turn_end`).
sha256: d147982128de14ab21fa8ae108531466105f8a07413c5d1892dca8fba56f06ef
