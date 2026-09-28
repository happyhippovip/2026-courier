# Checkpoint BATCH 2: Process Ownership & Resource Admission

## Erledigte Aufgaben

1. **Process Ownership fertiggemacht:**
   - Implementiert in `runtime/process_ownership.py`.
   - Die Klasse `ProcessOwnershipManager` trackt PID, PGID und assoziierte Ports.
   - Sie verfügt über Logik für `foreign process detection` (fremde PIDs filtern), `timeouts` (Zeitmessung), `orphan handling` (Simuliertes Auffinden von PGID 1 Prozessen) und `owned cleanup` (Rückgabe aller verwalteten PIDs zur Beendigung).
   - **Constraint "Keine Prozesse manipulieren"** wurde streng befolgt: Die Klasse gibt lediglich PID-Listen zur Planung zurück und greift nicht physisch per `os.kill` ein.

2. **Resource Admission implementiert:**
   - Implementiert in `runtime/resource_admission.py`.
   - Die Klasse `ResourceAdmissionController` prüft angefragte Ressourcen gegen die gesetzten Limits (CPU, RAM, Swap, Disk).
   - Das harte Limit `MAX_HEAVY_JOBS = 1` wurde im Standardprofil `ResourceQuotas` konfiguriert und wird im Controller explizit erzwungen.

3. **Konkrete Runbook-/Evidence-Dateien erstellt:**
   - **Runbook:** `ops/ai/live/RUNBOOK_BATCH_02.md`
   - **Evidence:** `ops/ai/live/EVIDENCE_BATCH_02.json`

## Deliverables
- [x] `runtime/process_ownership.py`
- [x] `runtime/resource_admission.py`
- [x] `ops/ai/live/RUNBOOK_BATCH_02.md`
- [x] `ops/ai/live/EVIDENCE_BATCH_02.json`
- [x] Paketanpassung in `runtime/__init__.py`

Alle Constraints (Kein git show, kein Ledger, keine physische Run-Ausführung, keine Prozess-Manipulation) wurden strikt eingehalten.
