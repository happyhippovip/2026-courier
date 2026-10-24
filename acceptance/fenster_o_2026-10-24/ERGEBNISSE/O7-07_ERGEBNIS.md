# O7-07 · B4 · Hop B ohne sha256 akzeptiert · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-07_test_hop_b_without_sha256.py` · sha256 `4d9ab19fb5f964cf89e3712e5a44e9add2f3f095361754380aa9465d82609a0e` |
| Marker | 3 × `xfail(strict=True, raises=AssertionError)` (sha256 fehlt / leer / kein Hex-64) + 3 Schutztests |
| Lauf auf Basis | `3 passed, 3 xfailed`, Exit 0; mit `--runxfail`: `hop B created: 201 task-…` (dreimal) |
| Kosten | 0 €, In-Process-Controller in tmp, kein Worker |

## Befund (VERIFIED)
- **Bridge: Schutz vorhanden, nicht gefunden (passed).** `scripts/ledger_v1_bridge.py:492-497` lehnt ein Upstream-Artefakt ohne gültige sha256 mit `input_unverified` ab. Dazu wird am Ende jede Datei gegen die Journal-sha256 geprüft (`:498-499`). Der Katalog-Input `tests/test_golden_ledger_bridge_ab.py` prüft nur den positiven A→B-Pfad.
- **Echter Defekt (P2):** Der Controller behandelt `params` als opak (`courier_core/controller.py:347-360`). Ein B-Task, dessen `params.inputs` **keine** gültige sha256 tragen, wird mit **201** angelegt. Der Hop-Vertrag „B nur mit {path, sha256}“ wird also nur von einem Client (der Bridge) durchgesetzt, nicht an der Controller-Grenze. Jeder andere Einlieferer (Intake, Wake-Inbox, manuelle POSTs) kann Hop B ohne Hash anlegen.

## Erwartung nach dem Fix
`create_task` lehnt `params.inputs` ab, sobald ein Eintrag keine 64-stellige Hex-sha256 oder keinen `artifacts/…`-Pfad hat (400 `invalid_request`).
sha256: aeacaf33031bfa52a6d33b1679daa675b16347885f881821c78c4111f7c9a403
