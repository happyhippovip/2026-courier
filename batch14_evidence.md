# Batch 14 Evidence

## Substep 1: Testabdeckung für Consume Chief Command (Missing Test)
- **Fehler:** Das zentrale Event-Ingestion-Skript `scripts/consume_chief_command.py` (Validierung und Weiterverarbeitung von Chief-Commands) verfügte über keinerlei Unit-Tests.
- **Fix:** `tests/test_consume_chief_command.py` erstellt. Die Tests decken sowohl den Erfolgsfall mit korrektem Hashing und Scope ab, als auch die gezielte Ablehnung bei einem `UNAUTHORIZED_REPO` (Scope Violation).
- **Check/Test:** Der Test wurde ausgeführt und läuft erfolgreich (`2 passed`).

## Substep 2: Testabdeckung für Build Channel Workflow Tasks (Missing Test)
- **Fehler:** Das Skript `scripts/build_channel_workflow_tasks.py` (Zuständig für das Auslesen der `social_channels.json` und Erzeugen von Night-Queue-Tasks) war ungetestet.
- **Fix:** `tests/test_build_channel_workflow_tasks.py` erstellt. Es wurde eine In-Memory Channel- und Workflow-Registry gemockt und verifiziert, dass die korrekte Anzahl an Tasks (inklusive Project-Mapping z.B. FruitKI-YouTube) generiert wird. Ebenso wird die Deduplizierung ("bereits QUEUED") getestet.
- **Check/Test:** Der Test wurde lokal erfolgreich ausgeführt (`2 passed`).

## Substep 3: Testabdeckung für Intake Dispatcher (Missing Test)
- **Fehler:** Das Skript `scripts/intake_dispatcher.py` (Nimmt neue Kundenaufträge entgegen und dispatcht diese via `gh workflow run` an den Revenue Worker) war komplett ungetestet.
- **Fix:** `tests/test_intake_dispatcher.py` erstellt. Der Test nutzt Monkeypatching, um die `subprocess.run` GitHub CLI-Calls (`gh workflow run` und `gh run list`) zu simulieren und verifiziert, dass die `central_state.json` Datei korrekt angelegt und mit dem geparsten `execution_ref` aktualisiert wird.
- **Check/Test:** Der Test läuft erfolgreich durch (`1 passed`).
