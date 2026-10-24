# O7-15 · G2 · Bridge-Renew ohne Grenze (R1) · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a`; zusätzlich WQ-1b v2 `a2a6dfabd` |
| Testdatei | `O7-15_test_bridge_reposts_rejected_forever.py` · sha256 `bd631aefd48e86ccc7c8a9c390ad708a9bbfad2e951118fb0ed25a9bbf372881` |
| Marker | 1 × `xfail(strict=True, raises=AssertionError)` + 1 Schutztest |
| Lauf | Basis: `1 passed, 1 xfailed`, Exit 0; WQ-1b v2: ebenso. Mit `--runxfail`: `3 POSTs for one refused mission` |
| Bezug | identisch mit V43-R1-Pin `V43_bridge_refusal_park_pin.diff` (sha256 `dbc11e2ea7ba86c72fe6d30507c3d223db250c131e3c17f1c8fb62763a6f4ed9`), hier gegen die Basis mit generischem 400 statt `cost_blocked` |
| Kosten | 0 €, Fake-HTTP |

## Zeilenprüfung (Katalog „ledger_v1_bridge.py Z. 342–369“)
Stimmt für die Basis: `:342-362` Claim und Mapping mit `posted: False`; `:365` `_post_task`; `:366-369` bei `rejected` nur `emit(skipped/rejected)` und `continue`. `_post_task` (`:713-745`) macht aus jeder Nicht-2xx-Antwort unterhalb 500 `{"rejected": True}`.

## Befund (VERIFIED)
Kein Status, kein Versuchszähler, kein BLOCKED: Eine abgelehnte Mission wird **bei jedem Durchlauf erneut gepostet** (3 Durchläufe ergeben 3 POSTs). Mit PR #846 tritt das zusätzlich bei jeder Abweichung zwischen Bridge-Spend-Gate und Controller-`cost_blocked` auf (V43, P1). Das ist die Ursache von O7-14.
- Schutz vorhanden (passed): Ein Duplikat-POST (200 `duplicate`) zählt nicht als Ablehnung; die Mission steht danach auf `POSTED`.

## Erwartung nach dem Fix (Minimalfix laut V43)
Bei 4xx außer 409 die Mission mit `status=BLOCKED`, Grund `controller_rejected:<code>`, stempeln und nicht erneut posten. **Reihenfolge:** vor oder zusammen mit #846 (#846 MERGE_GO=NO).
sha256: 7a0921abee8bb68e3502f469f1a0970e0385f977898edb41641fc9ae40d69686
