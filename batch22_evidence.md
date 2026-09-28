# Batch 22 Evidence

## Substep 1: Testabdeckung für Mac Worker Adapter (Missing Test)
- **Fehler:** Die Mac Worker Transport/Adapter Logik (`scripts/mac_worker_adapter.py`) hatte keine automatisierten Tests, obwohl sie kritische Outbox/Inbox-Pfade für das Host-Routing managt.
- **Fix:** `tests/test_mac_worker_adapter.py` geschrieben. Es wurde das erfolgreiche Ablegen und Auslesen von Worker-Resultaten getestet (inklusive Time-Sleep/Wait-Mocking). Ebenfalls wurde ein Timeout-Szenario simuliert, bei welchem das Skript korrekt ein `FAILED` Result mit dem Grund `TIMEOUT` in die Inbox legt.
- **Check/Test:** Testsuite erfolgreich (`2 passed`).

## Substep 2: Testabdeckung für Demo Workflow (Missing Test)
- **Fehler:** Das Demo-Orchestrierungs-Skript `scripts/run_demo_workflow.py` steuert als Integration-Wrapper die Chief- und Loop-Module und kopiert Artifacts für Live-Demos. Da es ein Integration-Tool ist, blieb es ungetestet und könnte unentdeckt kaputt gehen.
- **Fix:** `tests/test_run_demo_workflow.py` hinzugefügt. Es mockt den Curator, Commander und Loop und validiert, dass `run_live_demo` korrekte State-Verkettungen vornimmt und am Ende das erwartete `demo_evidence_manifest.json` erfolgreich wegschreibt.
- **Check/Test:** Testsuite erfolgreich (`1 passed`).

## Substep 3: Testabdeckung für Run Physical (Missing Test)
- **Fehler:** Das physische Runner-Skript für den Mac Host (`scripts/run_physical.py`) steuert die P3 Proof-Card Hashes und operativen State-Verifikationen des Couriers ohne Test-Harness (Gefahr auf Runtime-Bugs bei Refactorings).
- **Fix:** `tests/test_run_physical.py` erstellt. Simuliert (durch System-Mocks von Mem/CPU-Limits) einen erfolgreichen `execute_run1`-Lauf und überprüft, dass Exit-Code, Logs, Snapshot (mit gesetztem Status `SUCCESS` und Hash) deterministisch in das korrekte `evidence` Verzeichnis geschrieben werden.
- **Check/Test:** Testsuite erfolgreich (`1 passed`).
