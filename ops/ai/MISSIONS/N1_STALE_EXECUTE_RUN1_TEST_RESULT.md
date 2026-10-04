# N1 — Stale Execute RUN1 Test RESULT

## OUTPUT

**SCENARIO**: 
Ein Worker (MAC-01) hat Task A geclaimt, wird dann offline gemeldet (Stale), wodurch der Server durch `reclaim_stale` die Task unter Quarantäne (HUMAN_REQUIRED) stellt. Später reicht der alte Worker das Ergebnis doch noch ein.

**EXPECTED_STATE**: 
Der Server muss das veraltete Ergebnis ablehnen, da der Status des Tasks nicht mehr auf einen Result-Empfang für diesen Worker wartet (`DISPATCHED`).

**ACTUAL_OUTCOME (Statischer Beweis durch Test)**:
Die Logik in `server/app.py:373` (`if task.get("status") != "DISPATCHED": return jsonify({"error": "Task is not awaiting a result"}), 409`) sorgt dafür, dass das Resultat des stale Workers abgelehnt wird (HTTP 409 Conflict). Dies ist im Test-Skript `tests/test_n1_stale_execute.py` dokumentiert, das genau diesen Fall (Claim -> Quarantäne -> Result Submission -> 409 Rejection) erfolgreich verifiziert.

- **Task A schließt NICHT doppelt ab.**
- **Das veraltete Ergebnis überschreibt KEINE neueren Zustände.**
- **Keine Ledger-Korruption.**

**PHYSICAL_RUN_REQUIRED**: NO (Der Server blockiert dies deterministisch anhand der Status-Maschine. Der Python-Integrationstest `test_n1_stale_execute.py` deckt diesen Pfad ab, ohne dass ein physischer Run nötig wäre).
