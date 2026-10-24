# O7-05 · B3 · Provider DONE ohne Journal = final · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-05_test_done_without_journal.py` · sha256 `ebbacd01595b5c047bf8dba0318fb64e3dea6dd16664d4190c173f4f595c2176` |
| Marker | `xfail(strict=True, raises=AssertionError)` |
| Lauf auf Basis | `1 xfailed`, Exit 0; mit `--runxfail`: `released: ['WK1']`, Queue-Status `DONE` |
| Kosten | 0 €, nur Dateien |

## Befund (VERIFIED)
- **Bridge selbst: nicht gefunden.** Die Bridge schreibt zuerst das Ledger-Ereignis und stempelt erst danach `FINAL_DONE` (`scripts/ledger_v1_bridge.py:200-238`). Ein abgelehntes Ereignis bekommt keinen FINAL_DONE-Stempel (`:208-229`).
- **Echter Defekt (P2, Defense-in-Depth):** `courier_worker/queue_feed.py:125-128` gibt einen Workkey **endgültig als DONE frei**, sobald `ledger_bridge_state.json` `status: FINAL_DONE` meldet. Das Koordinations-Journal (`coordination_ledger.jsonl`) wird dabei **nicht** gefragt. Im Test steht im Journal nur ASSIGNED, die Mission ist nicht DONE, trotzdem wird der Workkey freigegeben. Auslöser kann eine veraltete oder wiederhergestellte State-Datei sein, ein fremder Writer oder ein Teil-Restore. Weil die Freigabe ein RELEASE ist, lässt sie sich nicht wieder öffnen (`courier_core/work_queue.py:166-167` `ALREADY_DONE`).
- `courier_core/journal.py` (Controller-Journal) wird von queue_feed überhaupt nicht gelesen. Der Feed bleibt laut Docstring absichtlich „file-only, never talks to the controller“ (`queue_feed.py:16-18`). Ein Fix kann deshalb das Koordinations-Ledger lesen (`reduce_store(store).get_mission(id).status == DONE`); das Ledger ist im Feed bereits geöffnet (`queue_feed.py:97`).

## Erwartung nach dem Fix
Eine Freigabe gibt es nur, wenn State `FINAL_DONE` **und** die Mission im Koordinations-Ledger `DONE` ist. Sonst bleibt der Workkey `CLAIMED`.
sha256: 2b784bca161e53d318ecf2aba33e5463265b19bfd280992daa63e0a58f86a937
