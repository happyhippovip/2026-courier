# M7 — RUN1_PROOF_CHAIN RESULT

## OUTPUT

| BEHAUPTUNG | EVIDENZ_DATEI | PRUEFER | BRUCH? |
|------------|---------------|---------|--------|
| GQ15 (A-executes-exactly-once) | `artifacts/run1/server_run1.log` | `verify_run1_evidence.py:27-36` (Zählt "Claimed task A" und "Result for task A") | **JA (Hoch)**: `run_1_mac.sh` speichert Logs in `logs/` statt `artifacts/run1/`. Pruefer findet die Datei nicht. |
| GQ16 (Expected-Hash-Survival) | `artifacts/run1/verifier_run1.log` | *Fehlt* | **JA (Hoch)**: `verify_run1_evidence.py` liest das Verifier-Log nicht und vergleicht keine Hashes. Log liegt zudem im falschen Ordner (`logs/`). |
| GQ17 (Server-Bytes/Hash Evidence) | `artifacts/run1/server_run1.log` & `worker_run1.log` | *Fehlt* | **JA (Hoch)**: Keine Überprüfung von Dateigrößen oder Hashes in `verify_run1_evidence.py`. |
| GQ18 (RECONCILED Terminal State) | `artifacts/run1/ledger_run1.db` | `verify_run1_evidence.py:16-24` (Nutzt `sqlite3`) | **JA (KRITISCH)**: Server nutzt JSON State (`app.py`), Pruefer versucht `sqlite3` aufzurufen. Zudem liegt die DB laut `run_1_mac.sh` im Root-Verzeichnis statt in `artifacts/run1/`. |
| GQ19 (RUN_1 Success Synthesis) | `artifacts/run1/RUN_1_SUCCESS_SYNTHESIS.md` | *Manuell/Prozess* | **JA (Mittel)**: `run_1_mac.sh` erzeugt eine leere Datei `artifacts/RUN_1_SUCCESS` per `touch`, anstatt ein beschreibendes Markdown-Dokument mit den erforderlichen Synthese-Daten zu generieren. |

Verdict: `RUN1_CHAIN_COMPLETE_STATIC: NO`

### Bruch-Liste nach Schwere:
1. **KRITISCH**: `verify_run1_evidence.py` nutzt `sqlite3`, aber das Courier-System speichert den State in JSON. Die Datenbank kann nicht geparst werden.
2. **HOCH**: Kompletter Verzeichnis-Mismatch. `run_1_mac.sh` schreibt nach `logs/` und ins Root, aber der Layout-Vertrag und `verify_run1_evidence.py` erwarten alles im Ordner `artifacts/run1/`.
3. **HOCH**: GQ16 und GQ17 (Hash-Prüfungen) sind in `verify_run1_evidence.py` überhaupt nicht implementiert. Die Behauptungen verpuffen unbewiesen.
4. **MITTEL**: GQ19 fordert ein Synthesis-Markdown, geliefert wird nur eine leere Marker-Datei.
