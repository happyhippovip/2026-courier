# Batch 23 Evidence

## Substep 1: Testabdeckung für Run Physical Restart (Missing Test)
- **Fehler:** Das Skript `scripts/run_physical_restart.py` für den RUN_2 Restart (ohne State-Replay) wurde nicht von der lokalen CI erfasst, was das Risiko von Regressionen bei Neustart-Simulationen erhöht.
- **Fix:** `tests/test_run_physical_restart.py` erstellt. Es simuliert einen korrekten RUN_1 Vorgänger-Status (Exitcode 0, `SUCCESS`) und validiert, dass RUN_2 ordnungsgemäß mit "RESTART_BOOT" startet und den Falsifizierbarkeits-Hash errechnet. Zudem wird getestet, dass ein manipulierter oder gescheiterter RUN_1 (Exitcode 1) RUN_2 präventiv blockiert (`Contamination guard triggered`).
- **Check/Test:** Testsuite erfolgreich (`2 passed`).

## Substep 2: Testabdeckung für Run Academy Demo (Missing Test)
- **Fehler:** Das Demo-Skript `scripts/run_academy_demo.py` verknüpft Teacher, Director und Steward zu einer deterministischen Output-Routine, lief aber in der CI als Blackbox ohne Unit-Verification.
- **Fix:** `tests/test_run_academy_demo.py` geschrieben. Es mockt alle drei beteiligten Akteure. So wird sichergestellt, dass das Demo-Skript die Methoden (`propose_lesson`, `review_lesson`, `evaluate_lesson`, `approve_adoption`, `record_worker_acknowledgement`) in der richtigen, deterministischen Sequenz aufruft und das `status: COMPLETED` Resultat zurückliefert.
- **Check/Test:** Testsuite erfolgreich (`1 passed`).

## Substep 3: Testabdeckung für Render Godot Movie (Missing Test)
- **Fehler:** Der Wrapper `scripts/render_godot_movie.py` steuert die Godot Movie Maker Engine deterministisch an (über GDScript Konstanten-Extrahierung). Dies war extrem fragil, da GDScript Regex-Parsings kaputt gehen können.
- **Fix:** `tests/test_render_godot_movie.py` generiert. Es prüft den Regex-Extraktor (`_required_constant`), indem es on-the-fly ein `test.tscn` und `test.gd` simuliert. Es stellt sicher, dass `DURATION` und `CAPTURE_FPS` sauber geparst und korrekt für das Command-Line-Interface in das `--quit-after` Argument (Frames) umgerechnet werden.
- **Check/Test:** Testsuite erfolgreich (`2 passed`).
