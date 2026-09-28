# Batch 17 Evidence

## Substep 1: Testabdeckung für Build Memory Update Proposal (Missing Test)
- **Fehler:** Das Skript `scripts/build_memory_update_proposal.py` (Zuständig für die autonome Erstellung von Memory-Proposals auf Basis von Task-Results) war ungetestet. Dies barg das Risiko von Schema-Verletzungen.
- **Fix:** `tests/test_build_memory_update_proposal.py` erstellt. Es testet die Extraktion von "verified facts" aus dem Task-Payload und überprüft, ob Status-Labels wie `EXTERNAL_STATUS` (z.B. bei TIKTOK oder FIVERR Nennung) und `VERIFIED_CURRENT` korrekt gesetzt werden. Zusätzlich wird die JSON-Schema Validierung (u.a. Vollständigkeit der über 12 Requirement-Felder) getestet.
- **Check/Test:** Der Test wurde lokal ausgeführt und erfolgreich abgeschlossen (`2 passed`).

## Substep 2: Testabdeckung für Courier Watchdog (Missing Test)
- **Fehler:** Der `scripts/courier_watchdog.py` (welcher stale Tasks reclaimt) war ungetestet.
- **Fix:** `tests/test_courier_watchdog.py` angelegt. Mit `unittest.mock` und `monkeypatch` wurde der Endlos-Loop unterbrochen (durch Simulation von `KeyboardInterrupt` im `time.sleep`) sowie der POST-Request gemockt, um sicherzustellen, dass die Reclaimed und Quarantined Werte sauber geparst und ausgegeben werden. Auch das Fehlen des API-Keys triggert einen korrekten `SystemExit`.
- **Check/Test:** Die Testsuite wurde ohne Hänger erfolgreich durchlaufen (`3 passed`).

## Substep 3: Testabdeckung für Publish Courier Result (Missing Test)
- **Fehler:** Das Skript `scripts/publish_courier_result.py` (Sicherheits-Gate für eingehende Codex-Resultate) hatte keinerlei Testabdeckung.
- **Fix:** `tests/test_publish_courier_result.py` hinzugefügt. Der Test stellt sicher, dass ungültige Payloads oder manipulierter Hash (SHA-256) über die Exception `payload hash mismatch` blockiert werden und dass nur exakte `EXPECTED` Envelope-Strukturen auf die Festplatte (`msg-task.result.json`) persistiert und an den GitHub-Output-Buffer gereicht werden.
- **Check/Test:** Die Testsuite läuft erfolgreich (`2 passed`).
