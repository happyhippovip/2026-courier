# Checkpoint BATCH 5: RUN_2 Vorbereitung

## Erledigte Aufgaben

1. **RUN_2 Restart Command Sheet erstellt:**
   - Dokument: `ops/ai/live/RUN_2_RESTART_COMMAND_SHEET.md`
   - Enthält die Richtlinien und Befehle für einen `controlled restart`.
   - Implementiert die Logik für `reconcile resume` mittels der Übernahme von `run_001` State.
   - Setzt `A persistence` voraus und verhindert jeglichen Neu-Lauf (`no A replay`), wodurch `A execution count=1` garantiert wird.
   - Plant den nahtlosen Übergang zu Phase B (`B continuation`).

2. **Evidence Layout erstellt:**
   - Dokument: `ops/ai/live/RUN_2_EVIDENCE_LAYOUT.json`
   - Definiert die zu erfassenden Metriken und Audits (Prüfung auf Execution Count == 1 für Phase A, Erwartung des Phase B Start-Markers).
   - Verweist explizit auf das Pre-Execution Gate: `RUN_1 == PASS`.

3. **Constraints beachtet:**
   - **Keine Ausführung:** Das Setup verbleibt strikt in einer planenden Vorbereitung. Es wurde nichts physisch gestartet.
   - **Gate:** Die Anforderung "Keine Ausführung vor RUN_1 PASS" ist in den Layouts und im Sheet verankert.

## Deliverables
- [x] `ops/ai/live/RUN_2_RESTART_COMMAND_SHEET.md`
- [x] `ops/ai/live/RUN_2_EVIDENCE_LAYOUT.json`
- [x] `ops/ai/live/GOOGLE_MAC_BATCH_05.md` (dieser Checkpoint)
