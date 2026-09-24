# P1: Übergabe und Ledger-Nutzung (Validation & Gaps)

## 1. Validierung der vorhandenen Funktionen

Der `agent_handoff_ledger.json` und die zugehörigen Skripte (`agent_handoff_ledger.py`, `courier_continue.py`) wurden im Mac-Scope tiefgehend analysiert und validiert:

- **Fail-Closed Integrität:** Die Validierungsschleife (`validate_bundle`) funktioniert extrem strikt. Manuelle oder fehlerhafte Skript-Eingriffe (wie durch `fix_all_hashes_correct.py`) führen sofort zu einem `ValidationError` (z.B. bei Diskrepanzen zwischen `changed_fields` und den tatsächlichen Diffs).
- **Multi-Threading Schutz:** `update_ledger` nutzt `atomic_write` und fängt `RevisionConflictError` sauber ab. Die Threads in `courier_continue.py` wiederholen den Lese-/Schreibvorgang, wenn ein anderer Thread den Ledger in der Zwischenzeit aktualisiert hat.
- **Freshness Check:** Der Ledger verweigert die Ausführung (`STALE`), wenn der `CURRENT_SHA` nicht mit dem `ACTUAL_SERVING_RUNTIME_SHA` übereinstimmt.

## 2. Konkrete Lücken in der tatsächlichen Benutzung

### A. Fehlender Kontext für "Chat-Gedächtnis-unabhängige" Rekonstruktion
Aktuell speichert der Ledger unter `UNPROVEN_EDGES` nur Strings (z.B. `"SALES PACKAGE"`). 
**Lücke:** Um einen Auftrag ohne Chat-Gedächtnis vollständig zu rekonstruieren, fehlen im Ledger die spezifischen Ausführungsanweisungen (`instruction`) und die Voraussetzungen (`required_capabilities` wie `mac` oder `windows`). Aktuell müssen diese aus dem Code (`parse_plan_to_graph` in `courier_continue.py`) oder aus Markdown-Dokumenten abgeleitet werden. 
**Lösung:** Der Ledger sollte eine Map von `EDGE_NAME -> TASK_SPEC` speichern, nicht nur eine Liste von Strings.

### B. Fehlende Zuweisungs-Stabilität
Wenn `courier_continue.py` startet, feuert es Tasks in einen Thread-Pool. 
**Lücke:** Es gibt keine persistente Zuweisung eines Tasks an eine `RUNTIME_IDENTITY` *während* der Ausführung (nur das Ergebnis wird an eine Identity gebunden). Ein abrupter Neustart weiß nicht, welcher Worker gerade welchen Task bearbeitet hat.

### C. Manuelle Eingriffe beschädigen den Hash-Baum
**Lücke:** Da die Historie kryptografisch verkettet ist (`previous_entry_sha256`), macht jede manuelle Änderung in der `central_state.json` oder im Ledger-File (z.B. um einen hängenden Task zu löschen) den Ledger unlesbar. Es fehlen CLI-Tools für sicheres, kryptografisch signiertes "Tombstoning" von kaputten Tasks.

## 3. Ergebnis
Der Ledger funktioniert als "Fail-Closed" Sicherheitsbarriere perfekt, benötigt aber für die echte **Multi-Agent-Resilienz** (Rekonstruktion nach Absturz ohne Chat) eine Erweiterung des Datenschemas (Task-Specs direkt in den Ledger) und CLI-Recovery-Tools.
