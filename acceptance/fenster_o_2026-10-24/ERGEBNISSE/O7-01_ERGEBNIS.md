# O7-01 · B1 CostGate · Auftrag ohne estimated_cost_eur · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` (geprüft 24.10.2026) |
| Testdatei | `O7-01_test_queue_feed_missing_cost.py` · sha256 `d61a8d9f4b81a5c2ffe58b2ed401577956f0e8fc0dd2a235ba411cb8c8bbe63a` |
| Marker | `xfail(strict=True, raises=AssertionError)` |
| Lauf auf Basis | `1 xfailed`, Exit 0; mit `--runxfail`: `AssertionError: assert 'CLAIMED' != 'CLAIMED'` |
| Kosten | 0 €, lokal, keine Provider-Aufrufe |

## Befund (VERIFIED)
- „Läuft trotzdem“ im Sinne von *wird beim Controller ausgeführt*: **nicht gefunden.** Die Bridge blockiert jeden neuen Dispatch ohne Schätzung (`scripts/ledger_v1_bridge.py:259-271` → `handoff_spend_block`, `scripts/handoff_spend.py:54-71`, `scripts/resource_policy.py:150-158`). Der Test prüft das als Schutzzeile mit: kein POST für WK1.
- **Echter Defekt:** `courier_worker/queue_feed.py:136-142` beansprucht und weist einen Workkey zu, ohne die Kosten zu prüfen. Danach erneuert `queue_feed.py:133` die Lease bei jedem Durchlauf. Weil die Bridge nur `blocked/UNKNOWN_COST` meldet und weder Mission noch Queue-Eintrag parkt, bleibt WK1 auf `CLAIMED`. WK2 hat vollständige Kosten und wird nie beansprucht. Die Kosten bleiben also fail-closed, aber die Queue steht.

## Erwartung nach dem Fix (der Test wird dann XPASS → strict-Fehler → xfail entfernen, C1-17)
WK1 ist nicht mehr `CLAIMED`, sondern geparkt bzw. blockiert, und es gibt genau einen POST, nämlich WK2.

## Fix-Richtung (nur Vorschlag, kein Code)
Kostenprüfung vor `queue.claim` in `queue_feed.py:137-141` (gleiche Entscheidung wie `handoff_spend_block`), alternativ BLOCKED-Stempel der Bridge plus Park im Feed (WQ-1b v2 `park`). Verwandt mit G2/O7-14.

## Ausführen
`cp O7-01_test_queue_feed_missing_cost.py <repo>/tests/ && python -m pytest tests/O7-01_test_queue_feed_missing_cost.py -q`
sha256: ca363d903c735bc52b7019ee38398901fcd4f500d1e06de11671870cc04d7e7f
