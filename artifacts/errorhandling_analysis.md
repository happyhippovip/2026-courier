# Courier Error Handling & Logging Analysis

## 1. Exception Handling
- Die Codebasis verlässt sich stark auf "bare excepts" (`except:` ohne spezifische Exception-Klasse). Es gibt mindestens 13 solcher Stellen in den Kernskripten. 
- Dies ist ein Anti-Pattern, da es auch System-Exceptions wie `KeyboardInterrupt` oder `SystemExit` fängt und verschluckt, was saubere Graceful Shutdowns verhindert.
- Beispiel im `Terminal-Wall-BACKGROUND.py`:
  ```python
  try:
      out = subprocess.check_output(["python3", QUEUE_SCRIPT, ...])
  except Exception as e:
      pass # Verschluckt potenziell wichtige Scheduler-Crashes
  ```

## 2. Logging
- Das Python `logging` Modul wird im gesamten Projekt nur in **6** Dateien importiert (bei über hundert Skripten).
- Der überwiegende Teil der Skripte nutzt einfache `print()`-Statements. Dies erschwert log-basierte Observability (wie Splunk, Datadog oder saubere File-Logs) enorm, da keine Level (INFO, WARN, ERROR) existieren und Stderr/Stdout oft vermischt werden.

## 3. Recovery & Problematische Zustände
- **Atomic Writes**: `work_queue.py` verwendet korrekte File-Locks (`filelock` Bibliothek) für den lokalen Queue-Zustand. Das ist eine große Stärke, um Race-Conditions bei 73 Workern zu verhindern.
- **Zombie-Prozesse**: Der Mac Supervisor (`Terminal-Wall-BACKGROUND.py`) verifiziert per `os.kill(pid, 0)` ob Worker-Prozesse noch leben. Wenn ein Prozess nicht mehr existiert, wird der PTY-Slot im Dashboard hart zurückgesetzt. Dies schützt vor Zombie-Einträgen.

## Fazit
Die funktionale Recovery-Logik (auf Architektur-Ebene) ist sehr robust und kollisionssicher. Die **technische Implementierung** (Logging-Hygiene, Bare Excepts, Silent Failures) ist jedoch extrem rudimentär und erschwert klassisches Debugging.
