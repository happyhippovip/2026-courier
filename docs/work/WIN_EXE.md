# Windows-EXE: Courier Desktop Hub

Stand dieser Datei: Build-Skript und Smoke-Logik sind im Repo. Ein `CourierHub.exe` wird hier nicht erzeugt. Dieser Host ist Linux. Es gibt keine Signatur und keinen Kauf.

Einstieg: `courier_hub/__main__.py`. Die EXE heißt `CourierHub.exe`, Konsole an, damit `--print-url` lesbar ist. Spec: `scripts/courier_hub_windows.spec`. Treiber: `scripts/build_windows_exe.py`.

Die Spec nennt die Hidden-Imports `courier_hub`, `courier_hub.server`, `courier_hub.model`, `courier_core`, `courier_core.build`, `courier_core.journal`, `courier_core.projection`, `courier_core.events`, `courier_core.state_machine`. Datenpfad: `courier_hub/static` nach `courier_hub/static`, weil der Hub `index.html`, `hub.js`, `hub.css`, `hub_core.mjs` und `favicon.svg` über `Path(__file__) / "static"` liest. `courier_overlay` ist ausgeschlossen. `codesign_identity` ist `None`.

## Linux, dieser Lauf

Echter Windows-Build: Skip. Grund: PyInstaller erzeugt `CourierHub.exe` nur auf Windows. Auf Linux wird kein EXE angelegt und keins behauptet.

```bash
python3 scripts/build_windows_exe.py --check
python3 scripts/build_windows_exe.py --dist dist/windows
python3 -m pytest tests/test_windows_exe_build.py -q
```

`--check` prüft die Spec. Der Build-Befehl druckt `SKIP:` und endet mit Exit 2. Der Pytest prüft die Spec, startet `python -m courier_hub`, liest `GET /hub/api/status` und beendet die Prozessgruppe samt Kind. Der Test `test_windows_exe_builds_and_answers` ist auf Nicht-Windows geskippt.

## Windows, exakte Schritte

1. Python 3.12, 64-bit, im `PATH`. Repo-Root als Arbeitsverzeichnis. Kein zweites Python davor.
2. Abhängigkeiten nur lokal, ohne Kauf:

```bat
python -m pip install --user pyinstaller
python scripts\build_windows_exe.py --check
```

`--check` muss `SPEC OK` drucken und mit Exit 0 enden. Wenn es `SPEC MISSING` druckt, nicht bauen.

3. Bauen. Das dauert. Ausgabe ist `dist\windows\CourierHub.exe`. Nicht signieren, nicht deployen, `dist\` nicht committen.

```bat
python scripts\build_windows_exe.py --dist dist\windows
```

4. Smoke: EXE startet, Hub antwortet, Prozessbaum endet.

```bat
python scripts\build_windows_exe.py --smoke dist\windows\CourierHub.exe --home %TEMP%\courier-hub-smoke
```

Das startet

```bat
dist\windows\CourierHub.exe --home %TEMP%\courier-hub-smoke --controller http://127.0.0.1:9 --port 0 --print-url
```

Erwartet eine Zeile `http://127.0.0.1:<port>/` und danach JSON mit `"controller": "not_set_up"`. Das ist die Hub-Antwort von `GET /hub/api/status`, wenn noch kein `courier.db` und kein Controller-Token liegen. Port 9 ist absichtlich geschlossen. Danach beendet das Skript die Gruppe mit `taskkill /F /T /PID`. Es darf kein `CourierHub.exe` mehr laufen.

5. Von Hand, dasselbe:

```bat
mkdir %TEMP%\courier-hub-smoke
dist\windows\CourierHub.exe --home %TEMP%\courier-hub-smoke --controller http://127.0.0.1:9 --port 8766 --print-url
```

In einer zweiten Konsole:

```bat
curl -s http://127.0.0.1:8766/hub/api/status
```

Dann die erste Konsole mit Strg+C schließen. Im Task-Manager darf kein Kindprozess von `CourierHub.exe` übrig sein.

Ein grüner Linux-Pytest ist kein Windows-Build und kein `VERIFIED`.
