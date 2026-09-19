# Courier Cannon V1

Öffnen: **Courier Cannon V1.cmd** in diesem Ordner. Das startet nur die neue
Cannon-Testoberfläche auf `http://127.0.0.1:8768/cannon`; keinen gemeinsamen
Courier-Dienst und keine persönliche Muse-Sitzung.

**Lokaler Testmodus:** Start erzeugt genau 5 oder 10 ausdrücklich angeforderte
harmlosen Testaufgaben. Der Streaming-Importer übergibt sie an die originalen
Courier-HTTP-Handler in einer isolierten Codekopie. Echte lokale Testprozesse
schreiben Textartefakte. Der bestehende Courier-Verifier prüft deren SHA256,
und der bestehende Core reconciliert. Das ist kein physischer Muse-/Provider-
oder Ledger-Abnahmenachweis.

- NORMAL ist der einzige freigegebene Modus: ein Prozess, höchstens eine unbeantwortete Aufgabe.
- Nach exakt gebundenem, gespeichertem und verifiziert/reconciliertem Ergebnis
  folgen mindestens fünf Sekunden Abstand. Erst danach werden READY und Controls
  erneut geprüft. Die fünf Sekunden sind keine Fertig-Erkennung.
- Pause: aktuelle Arbeit samt Result/Verifikation endet, dann PAUSED.
- Nach aktueller Aufgabe stoppen: aktuelle Arbeit endet, dann IDLE; Queue bleibt gespeichert.
- Fortsetzen: gleicher Test, gleicher kanonischer Goal, vorhandene Ergebnisse bleiben erhalten.
- Bei geändertem Cannon-Build erhält ein ausdrücklich gestarteter Test einen eigenen
  Fixture-Ordner. Vorherige Evidenz wird nicht gelöscht oder umgeschrieben.
- UNKNOWN oder fehlende Verifikation stoppt die gesamte Kette: RECONCILE_REQUIRED.
  Fehler blockieren bis zur Prüfung; ein unklarer Prozess wird nicht erneut gestartet.
- Nach Runtime-Neustart bleiben DONE und Results erhalten. Fortsetzen nimmt die
  gespeicherte Queue wieder auf; ein angebrochener Cooldown beginnt sicherheitshalber neu.
- Bei neuer Source-Version sind Start/Fortsetzen gesperrt, bis die eigene Runtime
  neu geladen wurde. Pause/Stop bleiben für laufende Aufgaben verfügbar.
- RED/YELLOW stoppen neue Starts; keine fremden Prozesse werden beendet.
- Ein leerer Durchlauf endet im Leerlauf. Keine Modelle werden zum Warten aufgerufen.

Der Browser aktualisiert den Status nur während seines eigenen Testprozesses.
Ein externer Verifier-/Provider-Wakeup ist in dieser Version **nicht** als
Produktionsverbindung abgenommen. Dauerlauf ist nur lokal mit Testprozessen
geprüft, solange App/Runtime laufen. Es gibt keinen 24/7-Hintergrunddienst.

## Befehle im neuen Workspace

```powershell
.\.venv\Scripts\python.exe -B app\server.py --cannon status
.\.venv\Scripts\python.exe -B app\server.py --cannon demo --count 5
.\.venv\Scripts\python.exe -B app\server.py --cannon pause
.\.venv\Scripts\python.exe -B app\server.py --cannon stop-after-current
.\.venv\Scripts\python.exe -B app\server.py --cannon import "C:\Pfad\notizen.txt" --import-id mein-import
```

Import ist **keine** Ausführungserlaubnis. TXT-Zeilen werden Notizen, JSONL-Records
bleiben unverändert erhalten. Explizite Ausführungsauswahl bindet Record-ID und
Fingerprint; sie ruft vorhandenes `/goals` mit einem stabilen `client_request_id`
auf. Gleiche ID mit anderem Inhalt wird als Konflikt protokolliert.
64 KiB je Record, höchstens 256 Records pro Standard-Importaufruf, maximal 100
ausgewählte Tasks pro Übergabe. Der Cursor setzt am bestätigten Byte fort.

## Prüfung und Grenzen

```powershell
Push-Location app\tests
..\..\.venv\Scripts\python.exe -B -m unittest -v test_cannon_selection test_cannon_overnight.OvernightTests test_cannon_v0
Pop-Location
.\.venv\Scripts\python.exe -B app\test_server.py
```

Die Tests kopieren ausschließlich Python-Code des vorhandenen Courier-Core.
Produktionszustand, Zugangsdaten und Provider bleiben außen vor. Test-Credentials
sind getrennte synthetische Werte. Keyring-Zugriff ist im Harness verboten.
Der Hintergrund-Reaper wird im Harness nicht gestartet; Claim-Wartezeit und
Verifier-Transport werden für einen begrenzten deterministischen Lauf ersetzt.
Eligibility, State-Persistenz, Result-Vertrag, Artefakt-Hashprüfung und Reconcile
kommen aus dem unveränderten Core. `TESTING=False` verhindert den Runtime-Testbypass.

Ein Core-Code-Delta überschreibt die vorhandene Fixture nicht. Es verlangt eine
separate versionierte Evidenzkopie. Tests sind kein Ersatz für unabhängige
Ledger-/Produktionsruntime-Abnahme.

Muse 1.3.0 unterstützt laut lokalem `exec --help` einen Headless-Lauf mit JSONL.
Der frühere Wrapper mit `muse execute/result/cancel` entspricht dieser Hilfe nicht.
Eine produktive Kopplung inklusive Result-Ereignissen, Schutz persönlicher
Muse-Dateien und unabhängiger Courier-Verifikation ist noch nicht nachgewiesen.
Live-Ausführung bleibt deshalb gesperrt. Es wurden nur `--help`, `exec --help`
und `--version` aufgerufen; keine Anmeldung oder Muse-Konfiguration geändert.

Abnahmepaket: `data/WINDOWS_CANNON_V1_ACCEPTANCE_PACKET.md`.
Unabhängige Abnahme: **PENDING**. Kein Ledger-Freeze wird hier behauptet.
