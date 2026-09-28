# Runbook: Process Ownership & Resource Admission

## Overview
Dieses Runbook beschreibt die Prozeduren zur Handhabung von Prozessen und Ressourcen-Zulassung (Admission) während eines Courier-Runs.

## 1. Process Ownership
- **PID / PGID Tracking:** Alle im Rahmen eines Runs gestarteten Prozesse müssen mit ihrer PID und Process Group ID (PGID) in der `ProcessOwnershipManager`-Instanz registriert werden.
- **Port-Zuordnung:** Sofern der Prozess einen Port bindet, wird dieser hinterlegt.
- **Foreign Process Detection:** Prozesse im System, die nicht der eigenen Run-Struktur angehören, werden durch `detect_foreign_processes` isoliert betrachtet, jedoch nicht manipuliert.
- **Timeouts:** Der `ProcessOwnershipManager` identifiziert Prozesse, deren Laufzeit das definierte Limit überschreiten.
- **Orphan Handling & Cleanup:** Zur Beendigung des Runs oder bei Fehlerfällen werden Child-Prozesse, die zu Waisen wurden (PGID 1), und alle registrierten Owned-Prozesse zur Bereinigung vorgesehen. **Achtung:** Es findet keine direkte `kill`-Ausführung statt.

## 2. Resource Admission
- Alle Workloads passieren den `ResourceAdmissionController`.
- Zulassungskriterien:
  - **CPU:** Max. Auslastung gemäss Kontingent.
  - **RAM:** Limitierter Speicher.
  - **Swap / Disk:** Zusätzliche Reservierungen.
  - **MAX_HEAVY_JOBS:** Strikt limitiert auf `1`.
- Jede Abweisung wird mit einem `reason` versehen, der geloggt wird.

## Operational Instructions
Da physische Prozessmanipulationen strikt verboten sind, agieren alle Tools in einem planenden / auditierenden Modus.
