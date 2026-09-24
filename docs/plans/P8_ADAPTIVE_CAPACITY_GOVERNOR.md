# P8: Adaptive Capacity Governor

## 1. Bestehender Einhängepunkt
Der Governor wird direkt in den neuen zentralen Supervisor (`scripts/mac_worker/Terminal-Wall-BACKGROUND.py`) in die `supervise_loop()` eingehängt. 
- Die Dispatch-Entscheidung (`Wenn Proof PASS -> start_next_task`) prüft, ob `active_workers < ADMITTED_CAPACITY`.
- Wenn freie Kapazität besteht, wird an IDLE-Slots dispatcht. Wenn nicht, bleiben Aufgaben `QUEUED` (Worker im Slot ruht oder Slot bleibt unbesetzt).

## 2. Benötigte Messwerte (Mac Native)
- **Memory Pressure:** `memory_pressure | grep "System-wide memory free"`
- **RAM & Swap:** `vm_stat` für Pages und `sysctl vm.swapusage` für echtes Swapfile-Wachstum.
- **CPU & Load Average:** `sysctl vm.loadavg` und `ps -A -o %cpu,command`.
- **WindowServer / Terminal:** CPU-Last dieser UI-Prozesse zur Erkennung von GUI-Lags.

## 3. Capacity-State-Modell
- **DESIRED_CAPACITY:** Konfigurierbares Limit (z.B. 64, 73 oder AUTO).
- **ADMITTED_CAPACITY:** Aktuell sicheres Limit (startet z.B. bei 4).
- **GOVERNOR_STATE:** 
  - `RAMPING` (stufenweise Erhöhung)
  - `HOLD` (Ressourcen stagnieren, keine weiteren Worker)
  - `BACKOFF` (Kritische Last, aktiver Abbau)
- **METRICS_SNAPSHOT:** Ringpuffer zur Deltamessung.

## 4. Ramp-up-Regel
- **Bedingung:** `GOVERNOR_STATE == RAMPING` und Ressourcen-Delta stabil (Swap-Wachstum < 5%, CPU Load < Threshold).
- **Aktion:** Nach Ablauf einer Messperiode (z.B. 30s) wird `ADMITTED_CAPACITY` verdoppelt (4 → 8 → 16 → 32) bis `DESIRED_CAPACITY` erreicht ist.

## 5. Backoff-Regel
- **Bedingung:** Swap wächst stark (>10% Delta), System Load übersteigt kritischen Schwellwert oder Memory Pressure warnt.
- **Aktion:** `GOVERNOR_STATE = BACKOFF`. `ADMITTED_CAPACITY` wird sofort um zz.B. 25% reduziert.
- **Abbau:** Keine brutalen Kills! Laufende `WORKING` Tasks bleiben unberührt. Sobald ein Worker `RESULT_READY`/`IDLE` meldet und `active_workers > ADMITTED_CAPACITY`, wird keine neue Arbeit dispatcht. Der PTY-Prozess (`screen`) wird ggf. kontrolliert beendet, um RAM freizugeben.

## 6. Kleinster Canary-Test
Ein isolierter Python-Test (`capacity_canary.py`), der das Systemprofil ausliest, das Governor-Modell simuliert, künstlich einen Load-Spike meldet und beweist, dass `ADMITTED_CAPACITY` sinkt, ohne dass bestehende PTY-Prozesse per SIGKILL beendet werden.
