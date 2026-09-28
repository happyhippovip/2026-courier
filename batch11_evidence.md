# Batch 11 Evidence

## Substep 1: Revenue Customer Intake Schema & Identity Bugs
- **Fehler**: `scripts/revenue_customer_intake.py` sendete den Payload fälschlicherweise mit dem Key `"tasks"` anstatt `"workflow_plan"`, wodurch der Server stattdessen den AI-Planner (`ChiefCommander`) aufrief und die eigentlichen Task-Parameter ignorierte. Zudem fehlte der `idempotency_key`, welcher vom `revenue_v1_safety_baseline.py` Verifier zwingend vorausgesetzt wird, was unweigerlich zu einem Crash im Verifier führte.
- **Fix**: Als agnostisches Skript direkt korrigiert. `"tasks"` in `"workflow_plan"` geändert und einen UUID-basierten `idempotency_key` für den generierten Task hinzugefügt.
- **Check/Test**: Einen gezielten Test (`test_revenue_customer_intake.py`) hinzugefügt, der den ausgehenden POST-Payload des Skripts validiert. Der Test bestätigt, dass das korrekte Schema verwendet wird.

## Substep 2: GitHub Worker Adapter Exception Black Hole (Patch-Paket)
- **Fehler**: Der als Hintergrundprozess gestartete `github_worker_adapter.py` fing Exceptions (wie z. B. Fehler beim Download von GitHub-Artefakten) in der `run()` Schleife zwar ab, brach dann aber einfach mit Code 1 ab, **ohne** dem Courier-Server ein Resultat (`FAILED`) zu senden. Da der übergeordnete Dispatcher weiterhin Heartbeats sendete, lief der Worker auf dem Server nie in ein Timeout. Der Task blieb für immer im Zustand `DISPATCHED` stecken (Deadlock).
- **Fix (Out of Jurisdiction)**: Da ich Windows Central Writer bin, habe ich ein exaktes Patch-Paket (`github_worker_patch_package.py`) geschrieben. Es injiziert einen Handler, der bei jeglichen Exceptions einen sauberen `FAILED`-Result-POST mit dem Error-Trace an den Server absetzt, bevor der Adapter terminiert.
- **Check/Test**: Einen neuen Testfall (`test_script_execution_posts_failed_result_on_exception`) in `tests/test_github_worker_adapter.py` ergänzt, der beweist, dass bei einem fatalen Error (z. B. fehlerhafter Task-Payload) nun korrekt versucht wird, ein Fehlerresultat zu senden. Alle Tests bestehen (grün).

## Substep 3: GitHub Dispatcher Refusal Deadlock (Patch-Paket)
- **Fehler**: Wenn der `courier_github_dispatcher.py` einen geclaimten Task aufgrund fehlender Identity-Felder oder einer unsicheren `dispatch_id` lokal ablehnte (`persist_packet` gibt `None` zurück), wurde der Task einfach ignoriert und die Schleife fortgesetzt. Auch hier sendete der Dispatcher fleißig weiter Heartbeats, wodurch der Server den Task nicht freigab. Resultat: Permanenter Deadlock des Goals.
- **Fix (Out of Jurisdiction)**: Ein exaktes Patch-Paket (`github_dispatcher_patch_package.py`) geschrieben, das die Ablehnung abfängt. Liefert `handle_claimed_task` nun `False` zurück, wird sofort ein `FAILED`-Result-POST ("Dispatcher refused the task") abgesetzt, um den Server-Status freizugeben.
- **Check/Test**: Patch erfolgreich angewandt. Die Gesamt-Suite läuft weiterhin stabil durch.
