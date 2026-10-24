# O7-09 · B5 Replay · gleiche Auftrags-ID zweimal ausgeführt · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-09_test_same_task_id_twice.py` · sha256 `80ca3ffc249e95949d40f5b42069b22c450477dfb071ac3405028946042677f4` |
| Marker | 1 × `xfail(strict=True, raises=AssertionError)` + 1 Schutztest |
| Lauf auf Basis | `1 passed, 1 xfailed`, Exit 0; mit `--runxfail`: `('ASSIGNED', 'task-101') == ('IDLE', None)` schlägt fehl |
| Kosten | 0 €, lokal, keine LLM-Aufrufe |

## Befund (VERIFIED)
- **Echte Ausführung: Schutz vorhanden, nicht gefunden.** Gleicher `idempotency_key` führt zu genau einem Task (201, danach 200 duplicate, gleiche `task_id`). Belegt durch `courier_core/controller.py:373-380`.
- **Echter Defekt (P2, Anzeige/Replay):** Laut `courier_overlay/event_bus.py:107-112` gilt **at-least-once**: Consumer „MUST fold idempotently (key on task_id + event_type, last wins)“. `OverlayStateMachine.process_event` (`courier_overlay/state_machine.py:19-39`) faltet aber stur in Reihenfolge, und `sync()` (`:41-46`) liest jedes Mal den ganzen Bus. Kommt ein bereits verarbeitetes `TASK_ASSIGNED` für das **abgeschlossene** task-101 ein zweites Mal an (Retry oder Replay), steht der Worker wieder auf `ASSIGNED` mit `current_task = task-101`. Das Overlay zeigt dieselbe Auftrags-ID also als zweite Ausführung. Die Replay-Harness (`courier_overlay/replay_harness.py:118-150`) erbt das.
- **Kein Befund, bewusst nicht getestet:** Doppelte *Einträge* nach `reset()` + `play_all()` erlaubt der Bus-Vertrag ausdrücklich („MUST NOT count records“, `event_bus.py:109-110`). Ein erster Testentwurf hat Einträge gezählt; ich habe ihn als vertragswidrig verworfen.

## Erwartung nach dem Fix
Ein abgeschlossener `task_id` bleibt beim Falten abgeschlossen; Duplikate eines früheren Ereignisses öffnen ihn nicht wieder.
sha256: f6add02e90f9c659148bd2c8ce137d9ad52214b55876cfe2465611805a219c1e
