# O7-06 · B3 · DONE ohne RESULT_ACCEPTED · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-06_test_done_without_result_accepted.py` · sha256 `b48272ff7103e5cdc8b0a22bae79be8750991f435800f0bf95f51029f2f42f66` |
| Marker | 1 × `xfail(strict=True, raises=AssertionError)` + 1 Schutztest |
| Lauf auf Basis | `1 passed, 1 xfailed`, Exit 0; mit `--runxfail`: `accepted_result_id: 'res-pending'`, status-lose Kopie wird zu `FINAL_DONE` abgeleitet |
| Kosten | 0 €, Fake-HTTP |

## Befund (VERIFIED)
- **Schutz vorhanden (passed):** Eine COMPLETE-Ansicht ohne `resolution=verified` erzeugt kein FINAL (`scripts/ledger_v1_bridge.py:415-419`, `_verified_result_id` `:551-560`). Ein Bridge-FINAL ohne RESULT_ACCEPTED: **nicht gefunden**.
- **Echter Defekt (P2, Feldsemantik):** RESULT_ACCEPTED setzt `accepted_result_id` nur im Verifier (`courier_core/state_machine.py:239`). Die Bridge schreibt jedoch in das Mapping-Feld `accepted_result_id` **jede** Ergebnis-ID der Controller-Ansicht. Bei einer nicht-COMPLETE-Ansicht greift `_result_id` (`ledger_v1_bridge.py:537-548`) auf `result_id`/`pending_result_id` zurück. Das geschieht in `_dispatch` (`:376-379`) und in `_feedback` (`:232`). Im Test steht nach dem Post `accepted_result_id = 'res-pending'`, obwohl es kein RESULT_ACCEPTED gab.
- **Folge:** Fehlt einer Kopie `status` (ältere State-Datei, Restore), dann leiten `_derive_mission_status` (`ledger_v1_bridge.py:927-934`) und die Hub-Karte (`courier_hub/automation_status.py:156-160`) daraus `FINAL_DONE` ab. Das ist DONE ohne RESULT_ACCEPTED. Im Test belegt: `derived == 'FINAL_DONE'`.

## Erwartung nach dem Fix
`accepted_result_id` im Mapping speichert nur `_verified_result_id(view)`; ausstehende IDs ggf. unter eigenem Feld (`pending_result_id`).
sha256: b93e1c47f8ddd87132660ea8fe9bb8002f97660d1bb8c10ff04d97437d134f3d
