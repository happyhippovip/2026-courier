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
- Inno Setup Fallback, falls `ISCC.exe` fehlt und `COURIER_INSTALL_INNO=1` gesetzt ist: `6.7.0`, Datei `innosetup-6.7.0.exe`, SHA256 `F45C7D68D1E660CF13877EC36738A5179CE72A33414F9959D35E99B68C52A697`. Eine abweichende Prüfsumme bricht den Build ab.
- `scripts/windows_worker/CourierSetup-v1.exe` SHA256: `853312F1CDFCC469A25547343B58B418C696317F22DB50165B7D0C4EE77425E8`, Größe 10586698 Bytes. Artefakt `courier-setup-exe` aus Lauf `39947845096`. Die Datei ist gitignoriert.

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
- Setup.exe vorhanden: PASS. Lauf [39947845096](https://github.com/happyhippovip/2026-courier/actions/runs/39947845096), Job `windows build`, Merge-Commit `4ec48dcdea8b87bb721f66b6a4c33053e790ebdb` für Head `a072dc3db`. Artefakt `courier-setup-exe`.
- Setup.exe SHA256: PASS. `853312F1CDFCC469A25547343B58B418C696317F22DB50165B7D0C4EE77425E8`, 10586698 Bytes, derselbe Lauf.
- Stiller Install und Uninstall: PASS. Derselbe Job, `windows-latest`. Log: `Silent installation and Start menu shortcut verified` und `Silent uninstallation verified successfully`. `%LOCALAPPDATA%\Courier\courier.db` blieb liegen.
- Startmenü in einer Windows-Sitzung: PASS. Derselbe Job. `Courier Symphony.lnk` zeigte auf die installierte `Courier.exe`.
- Update einer vorhandenen Installation: PASS. Derselbe Job. Log: `Silent upgrade verified`.
- Rollback der Programmdateien: PASS. Derselbe Job. Eine Datei auf dem Installationspfad ließ das Setup fehlschlagen, danach war `Programs\Courier` abwesend.
- Clean-Machine-Annahme: PASS auf dem frischen Runner `windows-latest`. Log: `CLEAN MACHINE: C:\Users\runneradmin\AppData\Local\Programs\Courier was absent before the setup EXE ran.`
- Privater Checkpoint: BLOCKED, HTTP 404
- ISCC: PASS. Der Runner hatte `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` bereits, Compiler-Engine Inno Setup 6.7.1. Der Fallback-Download von 6.7.0 lief in diesem Lauf nicht. Ohne vorhandenen Compiler und ohne `COURIER_INSTALL_INNO=1` bleibt der Build ein Fehler.

## Pytest

Host: Linux, Python 3.12, `pytest==9.1.1`.

`python3.12 -m pytest -q tests/test_windows_installer_package.py`

Ergebnis: `8 passed, 2 skipped in 0.07s`.

Der Skip von `test_courier_setup_silent_install_and_uninstall_lifecycle` auf Linux ist erwartet. Der stille Install läuft im Job windows-build, nicht auf dem Linux-Host.

Der CI-Job `windows build` auf Head `a072dc3db` (Merge `4ec48dcdea8b87bb721f66b6a4c33053e790ebdb`, Lauf `39947845096`) hat mit dem vorinstallierten Inno Setup 6.7.1 kompiliert. `CourierSetup-v1.exe` SHA256 `853312F1CDFCC469A25547343B58B418C696317F22DB50165B7D0C4EE77425E8`. Rollback, stiller Install, Upgrade, Startmenü-Verknüpfung und stiller Uninstall sind in dem Lauf grün. Der Customer-Reality-Lauf `39947845130` ist ebenfalls grün.
