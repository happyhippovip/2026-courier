# Batch 18 Evidence

## Substep 1: Testabdeckung für Validate Courier Task (Missing Test)
- **Fehler:** Das Skript `scripts/validate_courier_task.py`, welches am Front-Gate vor Codex die strukturelle Validität der Tasks absichert, war ungetestet.
- **Fix:** `tests/test_validate_courier_task.py` erstellt. Die Tests stellen sicher, dass alle "REQUIRED" Envelope Felder geprüft werden, dass der Hash über den Payload 100% kongruent berechnet wird (`canonical_hash`), und dass Task-Duplikate per File-Prüfung (`processed_dir.glob`) fehlschlagen und abgelehnt werden.
- **Check/Test:** Der Test wurde lokal ausgeführt (`2 passed`).

## Substep 2: Testabdeckung für Validate Chief Relay (Missing Test)
- **Fehler:** Die Logik zur Deterministic-Validation von "Antigravity Result" und "Chief Command" Events (`scripts/validate_chief_relay.py`) besaß keine Unit-Tests.
- **Fix:** `tests/test_validate_chief_relay.py` verfasst. Es werden sowohl COMMAND- als auch RESULT-Envelopes mit korrekten Inhalten eingespeist. Zusätzlich wird verifiziert, dass Manipulationen am Envelope (z.B. ein absichtlich falscher `payload_hash`) von der Validierungslogik sofort geblockt werden.
- **Check/Test:** Die Testsuite wurde erfolgreich durchlaufen (`3 passed`).

## Substep 3: Testabdeckung für Resolve Project Memory (Missing Test)
- **Fehler:** Das Skript `scripts/resolve_project_memory.py` extrahiert Lese-Auszüge (Kontext-Packages) aus dem `2026-project-memory`. Es war ungetestet, was das Risiko von unbeabsichtigten Secret-Leaks barg.
- **Fix:** `tests/test_resolve_project_memory.py` implementiert. Der Test prüft die korrekte Extraktion von Sections aus den MD-Dateien sowie das saubere Auslesen des Git-Commit-Hashes ohne Shell-Aufruf (`.git/HEAD`). Ein dedizierter Testfall (`test_resolve_project_memory_redaction`) verifiziert explizit, dass Passwörter und Tokens (wie `ghp_...`) im extrahierten Text zwingend durch `[REDACTED_CREDENTIAL]` überschrieben werden.
- **Check/Test:** Die Suite läuft fehlerfrei durch (`2 passed`).
