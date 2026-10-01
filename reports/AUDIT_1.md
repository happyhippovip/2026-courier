# AUDIT 1: Review Windows-Port (courier-cannon-win)

## Basis-Informationen
- **Ordner:** `C:\Users\lol\2026-workspace\courier-cannon-win` [BELEGT: PWD]
- **Branch:** `HEAD (no branch)` [BELEGT: `git status -s -b` Ausgabe `## HEAD (no branch)`]
- **Basis-SHA:** `6ca172accce22507e66478a26fbd84932c029eb6` [BELEGT: `git rev-parse HEAD` = `6ca172accce22507e66478a26fbd84932c029eb6`]
- **Arbeitsbaum-Status:** Der geplante Branch `windows/cannon-port-2026-09-23` existiert nicht als Git-Branch-Referenz [BELEGT: `git branch -a --list "*cannon*"` leer]; die Änderungen liegen als uncommitted Changes auf `6ca172ac` vor (`scripts/mac_adapter.py` modifiziert, `tests/test_cannon_windows_lock.py` untracked, `CANNON_WINDOWS_BERICHT.md` untracked) [BELEGT: `git status -s`].

---

## 1. Bewertung der Änderungen (git diff gegen 6ca172ac)

### Änderung 1: Entfernung von Top-Level `import fcntl` (`scripts/mac_adapter.py:14`)
- **Diff:** Zeile 14: `import fcntl` ersetzt durch `# fcntl/msvcrt are imported lazily inside _lock_stream (Windows port)`.
- **Korrekt?** JA [BELEGT: `fcntl` existiert unter Windows nicht; top-level Import wirft auf Windows sofort `ModuleNotFoundError`].
- **Mac-Verhalten unverändert?** JA [BELEGT: `fcntl` wird unter POSIX (`os.name != "nt"`) in Zeile 44 und 57 weiterhin importiert und genutzt].
- **Risiken:** Keine [BELEGT].

### Änderung 2: Hilfsfunktionen `_lock_stream` und `_unlock_stream` (`scripts/mac_adapter.py:28-59`)
- **Diff:** Neu eingeführt zur Plattformabstraktion des Datei-Locks.
  - POSIX: `fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)` bzw. `LOCK_UN`.
  - Windows: `msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)` bzw. `LK_UNLCK` nach `stream.seek(0)`.
- **Korrekt?** TEILWEISE [BELEGT]. Die Logik spiegelt das Muster aus `scripts/agent_handoff_ledger.py:624-645` wider. Für Windows ist das 1-Byte-Locking an Offset 0 der korrekte Weg für `msvcrt`.
- **Mac-Verhalten unverändert?** TEILWEISE [BELEGT]. Auf POSIX wird derselbe `flock`-Aufruf ausgeführt wie zuvor. Jedoch wird vor jedem Lock/Unlock `stream.seek(0)` aufgerufen (für `flock` unschädlich, für `msvcrt` erforderlich).
- **Risiken:** Gering für die isolierten Helferfunktionen an sich [BELEGT].

### Änderung 3: Lock-Initialisierung & Contention-Handling in `supervise()` (`scripts/mac_adapter.py:104-118`)
- **Diff:**
  - `self.state_dir.mkdir(parents=True, exist_ok=True)` vor Öffnen der Lockdatei [BELEGT: Zeile 104].
  - Öffnen mit `open("a+b")` statt `open("a")`, Seed von 1 Nullbyte (`b"\0"`), wenn Dateigröße 0 ist [BELEGT: Zeilen 105-109].
  - Abfangen von `BlockingIOError` (POSIX) und `OSError` (nur wenn `os.name == "nt"`, Zeilen 114-117).
- **Korrekt?** JA [BELEGT]. `msvcrt.locking` verlangt eine existierende Byte-Region (mindestens 1 Byte), andernfalls schlägt der Lock fehl. `msvcrt.locking` wirft bei Sperrkollision `OSError` (WinError 5 / EACCES), während `fcntl.flock` `BlockingIOError` wirft.
- **Mac-Verhalten unverändert?** JA [BELEGT: Wenn `os.name != "nt"`, wird ein unerwarteter `OSError` über `raise` weitergeworfen].
- **Risiken:** Keine wesentlichen [BELEGT].

### Änderung 4: KRITISCHER FEHLER – Vorzeitiges Entsperren vor `motor.supervise()` (`scripts/mac_adapter.py:126, 128`)
- **Diff:**
  - Zeile 126: `_unlock_stream(lock)` vor `return self._rebind(started)`.
  - Zeile 128: `_unlock_stream(lock)` unmittelbar VOR `return self._rebind(self.motor.supervise(max_cycles, idle_sleep))`.
- **Korrekt?** NEIN, KRITISCH FEHLERHAFT [BELEGT].
  - In `6ca172ac` stand `return self._rebind(self.motor.supervise(max_cycles, idle_sleep))` innerhalb des `with (self.state_dir / "supervisor.lock").open("a") as lock:`-Blocks OHNE manuellen Unlock. Da `self.motor.supervise(...)` vor dem `return` ausgewertet wird, blieb der Lock während der GESAMTEN Laufzeit der Supervisor-Schleife gehalten.
  - Durch den Aufruf von `_unlock_stream(lock)` in Zeile 128 wird die Sperre SOFORT freigegeben, BEVOR `self.motor.supervise()` überhaupt zu laufen beginnt.
- **Mac-Verhalten unverändert?** NEIN, AUF MAC EBENFALLS ZERSTÖRT [BELEGT]. Auf macOS wird Zeile 128 via `fcntl.flock(..., LOCK_UN)` ausgeführt. Auch auf dem Mac verliert der Supervisor damit jeglichen Instanzschutz während der Dauerlauf-Ausführung.
- **Beweis durch Testlauf:**
  - Testausführung von `test_second_supervisor_start_rejected`:
    Ausgabe: `AssertionError: assert second.supervise(max_cycles=1) == {"started": False, "reason": "supervisor_active"}` [BELEGT: Python-Testausführung].
  - `second.supervise()` wurde NICHT abgewiesen, sondern startete parallel zum ersten Supervisor.
  - Folge: Konkurrierender Schreibzugriff auf `motor.json`, Crash mit `PermissionError: [WinError 5] Zugriff verweigert: motor.tmp -> motor.json` [BELEGT: Traceback aus `cannon_motor.py:87`].
- **Risiken:**
  - Datenkorruption und Race Conditions bei parallelen Supervisor-Aufrufen [BELEGT].
  - Vollständiger Verlust der Invariante "Maximal 1 aktiver Supervisor pro State-Verzeichnis" auf ALLEN Plattformen (Windows & Mac) [BELEGT].

### Änderung 5: Neuer Test `tests/test_cannon_windows_lock.py`
- **Diff:** 54 Zeilen Testcode für Nebenläufigkeitsprüfung zweier Supervisoren via Threading.
- **Korrekt?** Konzeptionell sinnvoll, aber der Test schlägt gegen den aktuellen Code fehl [BELEGT: `AssertionError`].
- **Zusätzlicher Befund:** Fehlt `PYTHONPATH=.`, bricht der Test beim Import von `scripts.mac_adapter` mit `ModuleNotFoundError` ab [BELEGT: Pytest-Lauf].

---

## 2. Zusammenfassende Bewertung

| Kriterium | Status | Beleg |
|---|---|---|
| Windows-Import-Kompatibilität (`fcntl` entfernt) | ERFÜLLT | `scripts/mac_adapter.py:14` |
| Windows-Locking-Mechanismus (`msvcrt`) | ERFÜLLT | `scripts/mac_adapter.py:38-42, 105-109` |
| Mac-Verhalten unverändert | VERLETZT (Regression) | `_unlock_stream(lock)` in Zeile 128 hebt Lock auch auf Mac vor der Schleife auf |
| Supervisor-Exklusivität während Lauf | VERLETZT (Kritischer Bug) | Parallelstart führt zu Kollision & PermissionError in `cannon_motor.py` |
| Test `test_cannon_windows_lock.py` | FEHLSCHLAG | Schlägt mit `AssertionError` fehl |

---

## 3. Belegte Empfehlung zur Behebung

1. **Zeile 128 in `scripts/mac_adapter.py` entfernen** [BELEGT]:
   `_unlock_stream(lock)` darf NICHT vor `self.motor.supervise()` aufgerufen werden.
2. **Lock-Lebenszyklus an den `with`-Block binden** [BELEGT]:
   Entweder `_unlock_stream(lock)` erst im `finally:` nach Rückkehr aus `self.motor.supervise()` aufrufen oder das Verlassen des `with`-Blocks die Schließung und implizite/explizite Freigabe regeln lassen (wie in `scripts/agent_handoff_ledger.py:618-621`).

AUDIT FERTIG
