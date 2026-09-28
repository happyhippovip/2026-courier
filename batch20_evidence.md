# Batch 20 Evidence

## Substep 1: Testabdeckung für Run Context Sync (Missing Test)
- **Fehler:** Das Skript `scripts/run_context_sync.py`, das Context-Snapshots generiert und `attach_task_context` sowie `check_task_staleness` bereitstellt, wurde nie automatisiert getestet.
- **Fix:** `tests/test_run_context_sync.py` erstellt. Es verifiziert `check_task_staleness` (Rejects bei fehlendem Task-Context oder Mismatch-Hash) und `attach_task_context` (Korrekte Injection der Bounded Context Arrays wie latest_decisions).
- **Check/Test:** Testsuite erfolgreich (`4 passed`).

## Substep 2: Testabdeckung für Run Chief Commander (Missing Test)
- **Fehler:** Das zentrale Skript `scripts/run_chief_commander.py`, das eingehende Ideen zu Workflow-Plänen kompiliert, besaß keine Unit-Tests für `formulate_workflow_plan` und Block-Bedingungen.
- **Fix:** `tests/test_run_chief_commander.py` implementiert. Verifiziert die Plan-Erstellung (Workflow-ID mit `WF-CHIEF-` Prefix) via SmartResourceRouter und mockt den Steward für Context-Snapshots. Außerdem prüft ein Fall, dass bei "CONFLICT" Evaluierung durch den Curator die Idea blockiert wird (`BLOCKED_POLICY_CONFLICT`).
- **Check/Test:** Testsuite erfolgreich (`2 passed`).

## Substep 3: Testabdeckung für Run Content Production Pipeline (Missing Test)
- **Fehler:** Die Video- und Asset-Generierungspipeline `scripts/run_content_production_pipeline.py` lief komplett ohne Unit-Tests, wodurch Pfad- und Config-Parsing ungesichert war.
- **Fix:** `tests/test_run_content_production_pipeline.py` hinzugefügt. Es testet erfolgreich das Manifest-basierte Stage-Deduplizieren (wenn eine Stage bereits `COMPLETED` ist, wird der Executor übersprungen) sowie den `force_rerun=True` Flag, der ein explizites Re-Run der übersprungenen Stages auslöst.
- **Check/Test:** Testsuite erfolgreich (`2 passed`).
