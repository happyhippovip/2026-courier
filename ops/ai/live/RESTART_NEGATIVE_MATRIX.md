# Restart Negative Matrix

Diese Matrix definiert das erwartete Verhalten, strikt verbotene Verhaltensweisen, den Recovery-Pfad und die Evidence-Referenzen für kritische Fehler- und Neustartszenarien.

---

### 1. Restart Before Persist
*Ein Ausfall/Restart passiert, nachdem ein Schritt begonnen, aber bevor der State gespeichert wurde.*
- **Expected State:** Der aktuelle Schritt gilt als unvollständig/abgebrochen (`PENDING` oder `ORPHANED`).
- **Forbidden Behavior:** Fortschreiben in die nächste Phase oder Annahme des Teilschritts als komplett. Keine unvollständigen Artefakte dürfen validiert werden.
- **Recovery:** Vollständiger Re-Run des Schrittes via Reconciliation; vorherige (flüchtige) In-Memory Daten werden verworfen.
- **Evidence:** Logs der Reconciliation (`reconcile.log`) zeigen `No valid persistence found -> Re-executing step`.

### 2. After Persist
*Ein Restart passiert unmittelbar nachdem der State persistiert, aber bevor er validiert oder downstream propagiert wurde.*
- **Expected State:** State liegt vor (z.B. in `central_state.json`), markiert als `SAVED_UNVALIDATED`.
- **Forbidden Behavior:** Erneute Ausführung des physischen Jobs. Das Überschreiben der bereits persistierten Daten ohne vorherige Prüfung ist untersagt.
- **Recovery:** Reconciliation greift den State auf, bemerkt die Persistenz und triggert ausschließlich die nachgelagerte Validierungsphase.
- **Evidence:** `ownership.log` und `admission.log` zeigen Persistenz-Check erfolgreich an (`A persistence = TRUE`).

### 3. After Validation
*Ein Restart passiert, nachdem der State validiert wurde.*
- **Expected State:** State ist als `VALIDATED` markiert.
- **Forbidden Behavior:** Erneute Validierung oder erneuter Dispatch der Daten an den Verify-Schritt.
- **Recovery:** System überspringt den Job und die Validierung und geht direkt in den Verify- bzw. Propagations-Schritt über.
- **Evidence:** `run_manifest.json` zeigt `Validation: COMPLETED`.

### 4. After Verify
*Ein Restart passiert nach Abschluss der Verifikationslogik (Verify).*
- **Expected State:** Job-Lebenszyklus gilt logisch als abgeschlossen (`VERIFIED`).
- **Forbidden Behavior:** Rollback auf einen früheren Zustand.
- **Recovery:** Reconciliation nimmt den Block als final an, springt direkt zur Vorbereitung des Dispatch für die nächste Einheit.
- **Evidence:** Checksum / Signature in der Evidence Registry (`evidence_registry.json`).

### 5. After Reconcile
*Ein Restart passiert unmittelbar nach dem Abschluss des Reconcile-Prozesses, aber vor dem Dispatch des nächsten Jobs.*
- **Expected State:** Der Runtime Binding State ist exakt im Sync; Warteschlange für den nächsten Schritt ist gefüllt, aber unberührt.
- **Forbidden Behavior:** Verlust der Queue-Reihenfolge; doppeltes Reconcilen, was zu doppelten Queues führen würde.
- **Recovery:** Idempotenter Aufruf des Queue-Loaders, der existierende geplante Dispatches aufgreift.
- **Evidence:** `dispatch_queue.json` zeigt identische Länge vor und nach dem erneuten Boot.

### 6. After Dispatch
*Ein Restart passiert, nachdem ein Workload an einen Worker dispatched wurde, aber bevor dieser geantwortet hat.*
- **Expected State:** Job ist markiert als `DISPATCHED` oder `IN_PROGRESS`.
- **Forbidden Behavior:** Sofortiger Re-Dispatch, der zu "Split-Brain" (zwei Worker am selben Job) führt.
- **Recovery:** System wartet das definierte Timeout des `ProcessOwnershipManager` ab. Falls Timeout erreicht, wird der Status auf `FAILED/TIMEOUT` gesetzt und erst danach re-dispatched.
- **Evidence:** `timeout_monitor.log` oder `ProcessOwnershipManager` Orphan-Listen.

### 7. Worker Loss
*Der ausführende Worker stirbt unerwartet (PGID 1 orphan oder SIGKILL) während des Jobs.*
- **Expected State:** `ProcessOwnershipManager` detektiert, dass die registrierte PID nicht mehr existiert. Job-Status `ORPHANED`.
- **Forbidden Behavior:** Stilles Hängenbleiben in der Unendlichkeit (keine Erkennung des Worker-Todes).
- **Recovery:** Automatische Bereinigung via `plan_orphan_handling()`, Freigabe der Allocation (`MAX_HEAVY_JOBS`) im `ResourceAdmissionController`, Neu-Dispatch des Jobs.
- **Evidence:** `admission.log` (Ressourcenfreigabe) und `ownership.log` (Worker-Tod verzeichnet).

### 8. Stale Result
*Ein Worker liefert ein Ergebnis zurück, nachdem das Timeout abgelaufen und der Job bereits re-dispatched wurde.*
- **Expected State:** Job gilt in der Laufzeit bereits als abgebrochen oder von einer neuen Instanz bearbeitet. Resultat ist "stale".
- **Forbidden Behavior:** Überschreiben des States des neuen Workers durch das veraltete Resultat.
- **Recovery:** Ergebnis wird abgelehnt, isoliert (z.B. nach `artifacts/stale/`) und dem Worker wird ein `TERM`-Signal zugeordnet.
- **Evidence:** System Log: `Rejected stale result for Job X`.

### 9. Duplicate Result
*Zwei Antworten für exakt den gleichen Job-Abschnitt kommen an.*
- **Expected State:** Das erste erfolgreiche Resultat persistiert.
- **Forbidden Behavior:** Aufsummieren von Metriken oder unkontrolliertes Überschreiben (Data Race).
- **Recovery:** Die erste gültige Antwort (gemäß Timestamp und Validation) gewinnt. Das Duplikat wird protokolliert, in Quarantäne verschoben und hart ignoriert.
- **Evidence:** `quarantine/` Artefakte und Warnung im `system.log` über redundante Resultate.
