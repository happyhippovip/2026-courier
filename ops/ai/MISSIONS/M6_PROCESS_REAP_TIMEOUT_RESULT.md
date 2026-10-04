# M6 — PROCESS_REAP_TIMEOUT RESULT

## OUTPUT

`TIMEOUT_KILLS_CHILD: NO`

| SZENARIO | FOLGE | NUTZER_RISIKO |
|----------|-------|---------------|
| Regulärer Timeout (600s überschritten) | Exception wird abgefangen, Status "FAILED" an Server gemeldet. `powershell.exe` (Kind) wird **nicht** gekillt und läuft weiter. | **Hoch (Doppel-Wirkung):** Server retried den Task, während der Zombie-Prozess noch läuft. Beide Prozesse könnten gleichzeitig Zustand ändern (Race Condition, Korruption). |
| Worker Neustart per `stop.bat` | `python.exe` wird beendet. Da `stop.bat` kein `/T` (Tree) Flag nutzt, überleben alle laufenden `powershell.exe` Tasks als Waisen (Orphans). | **Hoch:** Alte Tasks laufen im Hintergrund unkontrolliert weiter, verbrauchen Ressourcen und können nachfolgende Tasks sabotieren. |

**Fix-Vorschlag:**
Im `except Exception`-Block in `daemon.py` (bzw. bei TimeoutExpired) muss explizit `process.kill()` (oder `terminate()`) aufgerufen und kurz mit `process.wait()` auf den sauberen Abschluss gewartet werden. Zusätzlich sollte in `stop.bat` das Flag `/T` (Tree) bei `taskkill` ergänzt werden, damit auch alle Kind-Prozesse (wie `powershell.exe`) verlässlich abgeräumt werden.
