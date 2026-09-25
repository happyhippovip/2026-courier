# Courier Architecture Analysis

## 1. Verzeichnisstruktur
- **`app/` / `server/`**: Beinhaltet die REST-API und den zentralen Server-Status (`app.py`, `ledger.py`, `goals.json`). Dies scheint der Haupt-Einstiegspunkt für synchrone HTTP-Kommunikation zu sein.
- **`scripts/`**: Das Herzstück der Architektur. Hier liegen alle Runner (`run_*.py`), der Scheduler (`work_queue.py`), sowie Worker-Scripts (`mac_worker/`, `windows_worker/`).
- **`runtime/` / `coordination/` / `work/` / `work-script/` / `queue-strike/`**: Verschiedene Verzeichnisse für temporäre State-Files, Logs, PTY-Aufzeichnungen und isolierte Worker-Umgebungen.

## 2. Kernmodule
- **Motor / Scheduler**: Implementiert primär in `scripts/work_queue.py` sowie `task_routing.py`. Er nutzt deterministisches File-Locking, um Claims kollisionsfrei zu vergeben.
- **Worker Supervisor**: `scripts/mac_worker/Terminal-Wall-BACKGROUND.py` ist der lokale Mac-Governor. Er pollt macOS-Metriken (Swap, Load, Memory Pressure) und drosselt den Start von Sub-Prozessen (`muse --yolo` oder `agy`), um das System nicht zu überlasten.
- **Ledger**: Der zentrale Zustand wird oft in `agent_handoff_ledger.json` (6.6MB) geschrieben, was eine Historie und Koordination über Agenten hinweg ermöglicht.
- **Verifier**: Verschiedene Skripte wie `check_*.py` und dedizierte Micro-Verifikationen in der Queue (`VERIFYING` State) bestätigen Artefakte.

## 3. Datenflüsse (Data Flow)
1. **Submission**: Eine Aufgabe wird per API oder CLI (`work_queue.py add`) ins System gespeist.
2. **Dispatching (Motor)**: Die Aufgabe liegt in der JSON-Queue (`READY`). Der Supervisor (`Terminal-Wall-BACKGROUND.py`) bewertet die Systemkapazität (`CapacityGovernor`). Wenn sicher, wird ein Claim-Versuch gestartet (`work_queue.py claim`).
3. **Execution**: Ein Worker-Prozess (`muse` oder `agy`) bekommt `COURIER_TASK_ID` injiziert und arbeitet den Task ab. Er schreibt seinen Fortschritt in lokale State-Files (wie `task_state.json` oder direkt in den Ledger).
4. **Verification**: Der Worker meldet `RESULT_READY`. Der Supervisor/Motor checkt das Artefakt (`proof_ref`). Bei Erfolg: `work_queue.py complete`.

## 4. State-Management
- **JSON**: `agent_handoff_ledger.json`, `goals.json`, `/tmp/courier_work_queue`. JSON ist das primäre Format für strukturierte Tasks und Claims.
- **TSV**: `state.tsv` (im Ordner `wall/`) speichert den PTY-Status der 73 Worker (MUSE-01 bis CLI-09) für das Dashboard.
- **SQLite**: Wird partiell für Caching oder spezifische Tests (`test_fast.sqlite3`, `test_edge.sqlite3`) genutzt, ist aber nicht die "Single Source of Truth".

## 5. Schnittstellen (Interfaces)
- **CLI**: `scripts/work_queue.py` wird extrem stark als CLI von den Bash/Screen-Prozessen aufgerufen.
- **IPC**: Kommunikation läuft über File-Locks (z.B. `.lock`-Dateien auf den JSONs) und Environment-Variablen (`COURIER_TASK_ID`).
- **REST-API**: `server/app.py` liefert vermutlich eine Dashboard-/Steuerungsschnittstelle für die gesamte Symphony, ggf. auch für Worker auf anderen Rechnern (Windows).

## 6. Architektur-Schwächen
- **Fragmentierung**: Es gibt hunderte `patch_*.py`, `check_*.py`, `fix_*.py` und `test_*.py` Skripte im Root-Verzeichnis (`/Users/user/Downloads/2026-courier`). Dies deutet auf inkrementelles "Monkey-Patching" hin, statt Module aufzuräumen.
- **JSON-Bottle-Neck**: Ein 6.6MB großes `agent_handoff_ledger.json`, das synchron gelesen/geschrieben und mit `.lock` geschützt wird, skaliert bei 73 hochfrequenten Workern schlecht.
- **Subprocess-Overhead**: Das ständige Polling durch `sysctl` und `ps` im Python-Supervisor (`Terminal-Wall-BACKGROUND.py`) verbraucht CPU.

