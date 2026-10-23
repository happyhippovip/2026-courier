# Windows Installer Release Candidate

Basis: `integration/v1` `d5b19f1dffe5f5478476bf090c522b38bfc7164e`.
Branch: `cursor/windows-installer-rc-be3a`.
Der divergierte Branch `grokbot/gb-windows-installer-exe-01` (`d52a565a31`) wurde nicht gemergt. Übernommen und korrigiert wurden nur das Inno-Skript, das Build-Skript und der Statiktest.

## Lease

Geprüft vor der Änderung: keine offene PR enthält `courier_installer.iss`. PR #783 besitzt `scripts/windows_worker/build_package.ps1` und `tests/test_windows_packaging_contract.py`; beide Dateien sind unverändert. Der einzige laufende Cloud-Agent in dieser Umgebung ist dieser Installer-Lauf. Eine Git-Datei-Lease gibt es im Stamm nicht. Die exklusive Schreibmenge dieses Laufs sind:

- `scripts/windows_worker/courier_installer.iss`
- `scripts/windows_worker/build_installer.ps1`
- `tests/test_windows_installer_package.py`
- `docs/v1/WINDOWS_INSTALLER_RC_MATRIX.md`
- eine Zeile in `.gitignore`

## Checkpoint

Das benannte private Checkpoint-Repository hat diesem Konto HTTP 404 geantwortet. BLOCKED. Der Inhalt wurde nicht gelesen und nicht in dieses öffentliche Dokument kopiert.

## Quellprüfsummen

- `scripts/windows_worker/courier_installer.iss` SHA256: `4f7986a789cdfc1678b064d9c6f23d3f5758825231f01bf5d6080ba3c8a3f876`
- `scripts/windows_worker/build_installer.ps1` SHA256: `7c59ad0abf792e764362062ad73028862d77c144aa15bfbd67d0515acbf1e0a9`
- Inno Setup Compiler: `6.7.0`, Datei `innosetup-6.7.0.exe`, SHA256 `F45C7D68D1E660CF13877EC36738A5179CE72A33414F9959D35E99B68C52A697`. Der windows-build-Job lädt sie nur, wenn `COURIER_INSTALL_INNO=1` gesetzt ist, und bricht ab, wenn die Prüfsumme abweicht.
- `scripts/windows_worker/CourierSetup-v1.exe` SHA256: steht in der Zusammenfassung des windows-build-Jobs für denselben Commit. Die Datei ist gitignoriert und wird als Artefakt `courier-setup-exe` hochgeladen.

## Matrix

- Installationspfad `%LOCALAPPDATA%\Programs\Courier`, identisch zu `install.ps1`: PASS, statischer Test
- Datenverzeichnis `%LOCALAPPDATA%\Courier` fehlt in `[UninstallDelete]`: PASS, statischer Test
- `PrivilegesRequired=lowest`, kein API-Key, kein LAN-Default: PASS, statischer Test
- Startmenü-Verknüpfung zeigt auf `{app}\Courier.exe`: PASS, statischer Test
- Stiller Lauf startet das Programm nicht (`skipifsilent`): PASS, nur als Skriptzeile
- Secret-Dateinamen unter `scripts/windows_worker/dist`: PASS, keine Treffer
- Credential-Marker im Dist-Inhalt: PASS, kein freistehendes `sk-`, kein Private-Key-Block, kein Token-Präfix. Das Teilwort in `task-` zählt nicht.
- `dist\install.ps1` und `dist\Courier.exe` weichen von den aktuellen Dateien neben dem Skript ab. Das Inno-Skript überschreibt beide nach `dist\*`: PASS, statischer Test
- `start.bat` bleibt die Dist-Kopie, weil sie CRLF ist: PASS, statischer Test
- Autostart ist eine abgewählte Aufgabe: PASS, statischer Test
- Setup.exe vorhanden: Nachweis ist der Job windows-build dieses Commits. Er kompiliert `CourierSetup-v1.exe` und lädt das Artefakt `courier-setup-exe` hoch. Fehlt die Datei, ist der Job rot.
- Setup.exe SHA256: Nachweis ist die Job-Zusammenfassung desselben windows-build-Laufs. Der Hash wird hier eingetragen, sobald der Lauf grün ist.
- Stiller Install und Uninstall: Nachweis ist derselbe Job auf `windows-latest`. `/VERYSILENT` muss nach `%LOCALAPPDATA%\Programs\Courier` installieren, und `unins000.exe` muss `Courier.exe` entfernen. `%LOCALAPPDATA%\Courier\courier.db` muss liegen bleiben.
- Startmenü in einer Windows-Sitzung: Nachweis ist derselbe Job. `Courier Symphony.lnk` muss auf die installierte `Courier.exe` zeigen.
- Update einer vorhandenen Installation: Nachweis ist derselbe Job. Dieselbe Setup-EXE läuft ein zweites Mal, `Courier.exe` muss vorhanden bleiben.
- Rollback der Programmdateien: Nachweis ist derselbe Job. Liegt eine Datei auf dem Installationspfad, muss das Setup ohne Exitcode 0 und ohne Verzeichnis `Programs\Courier` enden.
- Clean-Machine-Annahme: Nachweis ist der frische Runner `windows-latest`. Vor dem erfolgreichen Setup darf `Programs\Courier` nicht vorhanden sein.
- Privater Checkpoint: BLOCKED, HTTP 404
- ISCC: Nachweis ist derselbe Job. Gepinntes Inno Setup 6.7.0, SHA256 `F45C7D68D1E660CF13877EC36738A5179CE72A33414F9959D35E99B68C52A697`. Ohne `COURIER_INSTALL_INNO=1` bleibt ein fehlender Compiler ein Build-Fehler.

## Pytest

Host: Linux, Python 3.12, `pytest==9.1.1`.

`python3.12 -m pytest -q tests/test_windows_installer_package.py`

Ergebnis: `8 passed, 2 skipped in 0.07s`.

Der Skip von `test_courier_setup_silent_install_and_uninstall_lifecycle` auf Linux ist erwartet. Der stille Install läuft im Job windows-build, nicht auf dem Linux-Host.

Der CI-Job `windows build` installiert das gepinnte Inno Setup 6.7.0, kompiliert `CourierSetup-v1.exe` und prüft Rollback, stillen Install, Upgrade, Startmenü-Verknüpfung und stillen Uninstall. Der SHA256 der Setup-EXE steht in der Job-Zusammenfassung desselben Laufs.
