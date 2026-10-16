# Gate G4 — Outbox Restart and Recovery

Stand: 2026-10-16.
Owner: Courier Engine. `BUILD_IF_AUTHORIZED = JA`.
Kosten: 0.0 EUR. Kein externer API-Aufruf, kein Spend.

## Scope & Invarianten

Gate G4 verifiziert den Wiederanlauf nach Absturz oder Unterbrechung ohne Replay von bereits bestätigten Seiteneffekten:

1. **Absturz vor dem Effekt**: Ein noch offener Outbox-Eintrag wird beim Neustart genau einmal fortgeführt.
2. **Absturz nach dem Effekt**: Liegt ein Journal-Nachweis (`run/effect-journal.jsonl`) vor, wird die Aktion nicht erneut ausgeführt.
3. **Mehrfacher Neustart**: Wiederholtes Anlaufen führt offene Einträge genau einmal aus und überspringt bestätigte danach stabil.
4. **Idempotenz je Durchlauf**: Werden im selben Durchlauf mehrere Einträge mit identischem `effect_key` vorgefunden, wird der Effekt genau einmal ausgeführt und nachfolgende übersprungen.
5. **Erneuter Dispatch**: Ein neuer Dispatch-Eintrag für einen bereits bestätigten `effect_key` wird nicht ausgeführt.
6. **Korrupter Outbox-Eintrag (Fail-Closed)**: Ein ungültiger oder korrupter JSON-Eintrag bricht mit `OutboxRestartError` ab, wird nicht ausgeführt und nicht gelöscht.
7. **Beweisgebundenes Aufräumen**: `cleanup_confirmed` entfernt ausschließlich Einträge, deren Bestätigung im Journal nachgewiesen ist. Alle anderen Dateien und Nachbar-Artefakte bleiben unberührt.
8. **Fehlgeschlagener Effekt**: Ein Effekt, der während der Ausführung eine Exception wirft, wird nicht bestätigt und bleibt für einen späteren Versuch offen.

## Nachweis

```bash
pytest tests/test_outbox_restart.py -q
```

Ergebnis:
- **9 passed in 0.97s** (100% grün).
- Modul: `courier_worker/outbox_restart.py`
- Test: `tests/test_outbox_restart.py`
