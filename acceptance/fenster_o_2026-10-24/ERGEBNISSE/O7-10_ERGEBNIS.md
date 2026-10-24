# O7-10 · B5 Replay · Neustart spielt erledigten Auftrag erneut · Claude Opus (FENSTER 7)

| Feld | Wert |
|---|---|
| Basis | `integration/v1` = `81bbf224b0aeeca4a2b92db29dfc7220b707043a` |
| Testdatei | `O7-10_test_restart_replays_done_job.py` · sha256 `6d482d93eb50c79b769c97d092aa7d6251e68ae955e2aefe035f1ef50cd938d8` |
| Marker | 1 × `xfail(strict=True, raises=AssertionError)` + 1 Schutztest |
| Lauf auf Basis | `1 passed, 1 xfailed`, Exit 0; mit `--runxfail`: `1 new dispatch(es) for a job that already ran` → `['gh', 'workflow', 'run', 'revenue_v1_baseline.yml', …]` |
| Kosten | 0 €, `subprocess.run` gemockt: kein gh, kein Netz |

## Befund (VERIFIED)
- **Schutz vorhanden, nicht gefunden:** Ist der Auftrag als ADMITTED erfasst, startet ein Neustart keinen zweiten Dispatch (`tests/test_queue_redispatch_skip.py:51-64`, Katalog-Input; `scripts/queue_processor.py:10-29`). Innerhalb der Grace-Zeit übernimmt ein Neustart den vorhandenen Lauf (Schutztest, `scripts/intake_dispatcher.py:258-268, 284-301`).
- **Echter Defekt (P1, Kundenauftrag läuft doppelt):** Der Absturz passiert, nachdem `gh workflow run` erfolgreich war, aber bevor ADMITTED gespeichert wurde. Zurück bleibt ein `DISPATCHING`-Marker. Nach `INTAKE_DISPATCH_GRACE_SECONDS` = 300 s (`intake_dispatcher.py:25`) gilt dieser Marker als „tot“ (`:269-283`: „A stale marker means the old attempt is dead“). Der Neustart ruft dann **erneut `gh workflow run`** auf, **ohne vorher** nach dem schon existierenden Lauf zu suchen (`resolve_execution_ref`, `:85-114`). Im Test ist dieser Lauf vorhanden (`databaseId 777`, erstellt nach `dispatched_at`). Trotzdem gibt es einen zweiten Dispatch.

## Erwartung nach dem Fix
Bei veraltetem Marker zuerst `resolve_execution_ref(…, dispatched_at)` aufrufen. Bei genau einem Lauf: übernehmen (adopt). Bei null Läufen: einmal neu dispatchen. Bei mehreren: fail-closed, Mensch entscheidet.
sha256: ed643c0bd2222450fcd4b019cb77452eeeb4d9e983a31ba716e2081c2e2ec034
