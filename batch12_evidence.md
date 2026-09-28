# Batch 12 Evidence

## Substep 1: GitHub Dispatcher Respawn Loop Fix (Bug Fix)
- **Fehler:** In `scripts/courier_github_dispatcher.py` übersprang `resume_pending()` nur den Status `POSTED`, nicht aber den in Batch 11 hinzugefügten Status `POSTED_FAILED`. Dies führte bei einem Absturz des Adapters zu einem unendlichen lokalen Respawn-Loop, bei dem der Dispatcher denselben fehlgeschlagenen Task endlos neu startete.
- **Fix:** `if status in ("POSTED", "POSTED_FAILED"): continue` hinzugefügt, sodass fehlgeschlagene Tasks wie gewünscht beendet bleiben und nicht neu gespawnt werden.
- **Check/Test:** Die Schleife iteriert nun korrekt über beide terminalen Zustände.

## Substep 2: Revenue Worker Adapter Schema Kompatibilität & Fehlerbehandlung (Bug Fix)
- **Fehler:** `scripts/revenue_worker_adapter.py` lud das Artefakt (`revenue_artifacts.zip`) fälschlicherweise als base64 direkt im Body von `/tasks/result` hoch und ließ sämtliche Pflichtfelder (`goal_id`, `dispatch_id`, `run_id`, `result_id`) des `DurableResult`-Schemas aus. Zudem wurden Abstürze des Bash-Befehls nicht als `FAILED`-Ergebnis an den Server gesendet, was in einem Deadlock auf dem Server endete.
- **Fix:** Der Adapter lädt das Artefakt nun korrekt über den unabhängigen `/artifacts` Endpunkt als `application/octet-stream` inklusive X-Courier-Artifact Headern hoch. Die Antwort wird genutzt, um ein Schema-konformes `DurableResult` Array mit `artifact_id` zu konstruieren. Zudem wird im `except subprocess.CalledProcessError:` Block nun ein `FAILED` Status gepostet.
- **Check/Test:** `test_revenue_worker_adapter.py` hinzugefügt, um die korrekte Payload-Generierung zu verifizieren (Test bestanden).

## Substep 3: Test für Courier Verifier ergänzt (Missing Test)
- **Fehler:** Es fehlte jegliche Testabdeckung für `scripts/courier_verifier.py`, insbesondere für die Validierungslogik `verify_artifacts`.
- **Fix:** Die Datei `tests/test_courier_verifier.py` wurde neu erstellt, um den Erfolgsfall von `verify_artifacts` inklusive korrektem Fetching (`fetch_artifact` Mocking) sowie den Fehlerfall bei fehlenden Artifact-Metadaten (`missing artifact_id`) abzusichern.
- **Check/Test:** Die Tests laufen erfolgreich in der Suite durch und erfüllen die Vorgabe "Wenn ein Test fehlt: gezielten Test ergänzen".
