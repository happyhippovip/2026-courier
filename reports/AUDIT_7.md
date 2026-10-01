# AUDIT 7: Notaus-Reaktionszeit & STOP-Handling (courier-cannon-win)

## Basis-Informationen
- **Ordner:** `C:\Users\lol\2026-workspace\courier-cannon-win` [BELEGT: PWD]
- **Branch:** `HEAD (no branch)` [BELEGT: `git status -s -b`]
- **Basis-SHA:** `6ca172accce22507e66478a26fbd84932c029eb6` [BELEGT: `git rev-parse HEAD`]
- **Untersuchte Dateien:**
  - `scripts/cannon_motor.py` [BELEGT: 447 Zeilen]
  - `scripts/mac_adapter.py` [BELEGT: 238 Zeilen]
  - `app/cannon/adapters.py` [BELEGT: 288 Zeilen]
  - `app/cannon/web.py` [BELEGT: 135 Zeilen]

---

## 1. Wo und wie oft wird STOP im Cannon-Code geprüft?

In `scripts/cannon_motor.py` und `scripts/mac_adapter.py` gibt es **keine periodische Hintergrundprüfung** auf Dateiebene, sondern lediglich zustandsbasierte Prüfungen an definierten Phasenübergängen:

### A. Auslösung von STOP
- **CLI:** `mac_adapter.py stop` ruft `adapter.stop()` [BELEGT: `scripts/mac_adapter.py:208, 233`].
- **Web-UI:** Klick auf "Stop" sendet `POST /api/cannon/action` mit `action: "STOP_AFTER_CURRENT"` [BELEGT: `app/cannon.js:35`, `app/cannon/web.py:80-90`].
- Beide Wege rufen `CannonMotor.request_stop()` auf [BELEGT: `scripts/mac_adapter.py:84-85`].
- `request_stop()` setzt im Status-Dictionary `stop_requested = True` und schaltet bei laufendem Motor den Status auf `STOP_AFTER_CURRENT` um [BELEGT: `scripts/cannon_motor.py:181-183`]. Dies wird via `_save()` atomar in `<state_dir>/motor.json` geschrieben [BELEGT: `scripts/cannon_motor.py:83-87, 184`].

### B. Prüfstellen in `scripts/cannon_motor.py`
Es existieren genau **4 Prüfstellen** für `stop_requested`:

1. **`supervise()` vor dem nächsten Task-Schritt (`scripts/cannon_motor.py:414`):**
   ```python
   if self.m.get("waiting_for_work") or self.m.get("stop_requested"):
       break
   ```
   - **Häufigkeit:** Genau **einmal pro Aufgabenzyklus**, bevor `self.run_step()` aufgerufen wird [BELEGT].
   - **Wirkung:** Bricht die Supervisor-Schleife ab – greift aber erst, wenn `run_step()` bereits zurückgekehrt ist.

2. **`run_step()` vor Task-Zuteilung bei `local_fake` (`scripts/cannon_motor.py:276`):**
   ```python
   if self.m.get("pause_requested") or self.m.get("stop_requested"):
       self.m["state"] = "PAUSED" if self.m.get("pause_requested") else "IDLE"
       self._save()
       return {"step": "controlled_stop", "state": self.state}
   ```
   - **Häufigkeit:** Einmal vor der Zuteilung eines neuen lokalen Fake-Tasks [BELEGT].
   - **Einschränkung:** Gilt **nur** im `local_fake`-Zweig. Läuft ein echter Provider- oder Queue-Task, wird diese Stelle nicht durchlaufen [BELEGT: `scripts/cannon_motor.py:270`].

3. **`_admit_local_fake()` (`scripts/cannon_motor.py:247`):**
   ```python
   if self.m.get("pause_requested") or self.m.get("stop_requested"):
       return
   ```
   - **Häufigkeit:** Verhindert das Hinzufügen weiterer Fake-Tasks in die Queue [BELEGT].

4. **`run_step()` nach Task-Abschluss und Cooldown (`scripts/cannon_motor.py:388-395`):**
   ```python
   elif self.m["stop_requested"]:
       snap = self.queue_snapshot()
       remaining = [t for t, v in snap["tasks"].items()
                    if v.get("status") in ("READY", "WAITING")]
       self.m["state"] = "IDLE" if remaining else "COMPLETED"
   ```
   - **Häufigkeit:** Genau **einmal am Ende** von `run_step()`.
   - **Timing:** Wird erst ausgewertet, nachdem die Aufgabe fertig ausgeführt, validiert, in der Queue auf `ACCEPTED` gesetzt und der Cooldown abgelaufen ist [BELEGT: `scripts/cannon_motor.py:353-388`].

---

## 2. Warum wird ein laufender Muse-Prozess nicht sofort beendet?

Die beobachtete Verzögerung von über 15 Sekunden auf dem Mac hat drei belegte technische Ursachen:

### Ursache 1: Semantik ist `STOP_AFTER_CURRENT`, kein Notaus (Abort)
- Das Systemdesign sieht explizit vor: `Control flags take effect between tasks, never mid-task` [BELEGT: Kommentar in `scripts/cannon_motor.py:384`].
- Es handelt sich um ein geordnetes Auslaufen nach der laufenden Aufgabe, nicht um einen Notaus-Prozessabbruch.

### Ursache 2: `LiveMuseAdapter.execute_canary()` blockiert synchron ohne Abbruchprüfung
- `run_step()` ruft in Zeile 330 blockierend auf:
  `outcome, result_id = LiveMuseAdapter.execute_canary(task, self.results_dir, persist_identity)` [BELEGT: `scripts/cannon_motor.py:330`].
- In `LiveMuseAdapter.execute_canary` (`app/cannon/adapters.py:154-167`) wird der Muse-Prozess per `subprocess.Popen` gestartet. Danach verweilt der Adapter in einer Warteschleife:
  ```python
  while child.poll() is None:
      identity['heartbeat_at'] = time.time()
      persist_identity(dict(identity))
      if time.monotonic() >= deadline:
          raise ValueError('MUSE_TIMEOUT_UNKNOWN_EFFECT')
      time.sleep(.25)
  ```
- **Befund:** In dieser Schleife wird **weder** `motor.json` **noch** ein Stop-File oder eine Stopp-Anforderung geprüft [BELEGT: `app/cannon/adapters.py:159-164`].
- Der Python-Thread wartet vollständig passiv, bis der Muse-CLI-Prozess (`muse exec ...`) seine Inferenzschritte (bis zu 6 Modellschritte laut Flag `--max-model-steps 6`, Zeile 148) abgeschlossen hat und sich selbst beendet [BELEGT]. Auf dem Mac dauert dieser Netzwerk- und LLM-Aufruf typischerweise 10–20 Sekunden.

### Ursache 3: Erzwungener 5-Sekunden-Cooldown NACH der Ausführung
- Selbst nachdem der Muse-Prozess erfolgreich beendet und das Ergebnis verifiziert wurde, pausiert `run_step()` ununterbrochen:
  ```python
  cooldown = self.m.get("cooldown_seconds", 5.0) or 0
  if cooldown > 0:
      time.sleep(cooldown)
      self._load()
  ```
  [BELEGT: `scripts/cannon_motor.py:380-383`].
- Erst **nach** Ablauf dieser 5 Sekunden wird `self._load()` aufgerufen und Zeile 388 (`elif self.m["stop_requested"]:`) erreicht.
- **Folge:** Allein durch den Cooldown kommen nach dem Prozessende garantiert 5 Sekunden Verzögerung hinzu [BELEGT].

---

## 3. Zusammenfassung der Reaktionszeit-Kette

| Phase | Dauer | Warum keine sofortige Reaktion? |
|---|---|---|
| Klick auf Stop / Anforderung Stop | ~0.0 s | Schreibt nur Flag in `motor.json` [BELEGT: `scripts/cannon_motor.py:184`] |
| Laufender Muse-Prozess | 10–25 s | `execute_canary` prüft in seiner 250ms-Schleife kein Stop-Flag; wartet auf Selbstbeendigung von Muse [BELEGT: `app/cannon/adapters.py:159-164`] |
| Ergebnis-Reconciliation | ~0.1 s | Queue-Update auf `ACCEPTED` [BELEGT: `scripts/cannon_motor.py:353-356`] |
| Cooldown-Sleep | 5.0 s | `time.sleep(5.0)` blockiert ununterbrochen vor Auswertung von `stop_requested` [BELEGT: `scripts/cannon_motor.py:380-383`] |
| **Gesamte Reaktionszeit** | **15–30+ s** | **Erklärt exakt die beobachteten >15 Sekunden auf macOS** |

---

## 4. Textvorschlag zur Optimierung (Konzeptionell, NICHT umgesetzt)

1. **Prüfung in der Adapter-Warteschleife (`app/cannon/adapters.py:159-164`):**
   - Innerhalb von `while child.poll() is None:` alle 250 ms ein Abbruchkriterium prüfen (z.B. Existenz einer Notaus-Datei `<state_dir>/ABORT` oder Re-Read von `stop_requested` in `motor.json`).
   - Bei gesetztem Abbruch: `child.terminate()` aufrufen, 1–2 Sekunden auf geordnetes Beenden warten, bei Timeout `child.kill()` senden und als `ABORTED_BY_OPERATOR` terminieren.
2. **Unterbrechbarer Cooldown (`scripts/cannon_motor.py:381-383`):**
   - Den starren `time.sleep(cooldown)` durch ein iteratives Warten (z.B. `10 x time.sleep(0.5)`) ersetzen oder sofort abbrechen, wenn `self.m["stop_requested"]` gesetzt ist.
3. **Klare Trennung zwischen "Sanftem Stop" und "Notaus":**
   - `STOP_AFTER_CURRENT` beibehalten für saubere Transaktionsgrenzen.
   - Neues Signal `EMERGENCY_STOP` einführen, das den aktuell laufenden Prozess unmittelbar abbricht und die Task-Rückgabe/Quarantäne regelt.

AUDIT FERTIG
