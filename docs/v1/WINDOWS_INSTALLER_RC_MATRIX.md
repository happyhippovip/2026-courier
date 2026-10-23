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
- `scripts/windows_worker/build_installer.ps1` SHA256: `92024ffda3e47abdeebc065c97d2c348f5f6209fb4b3f8d9f1da50ddc25aea98`
- `scripts/windows_worker/CourierSetup-v1.exe` SHA256: UNPROVEN. Die Datei wurde hier nicht erzeugt.

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
- Setup.exe vorhanden: UNPROVEN
- Setup.exe SHA256: UNPROVEN
- Stiller Install und Uninstall: UNPROVEN
- Startmenü in einer Windows-Sitzung: UNPROVEN
- Update einer vorhandenen Installation: UNPROVEN. Dieselbe AppId und `UsePreviousAppDir=yes` stehen im Skript.
- Rollback der Programmdateien: UNPROVEN. Es gibt keine aufbewahrte Vorversion.
- Clean-Machine-Annahme: UNPROVEN
- Privater Checkpoint: BLOCKED, HTTP 404
- ISCC auf diesem Host: BLOCKED, `iscc` fehlt und wird nicht heruntergeladen
- Installation oder Deinstallation auf diesem Host: BLOCKED, nicht autorisiert

## Pytest

Host: Linux, Python 3.12, `pytest==9.1.1`.

`python3.12 -m pytest -q tests/test_windows_installer_package.py`

Ergebnis: `8 passed, 2 skipped in 0.07s`.

Die Skips sind `CourierSetup-v1.exe` und der stille Install/Uninstall. Ein Skip ist kein PASS.

Der CI-Job `windows build` auf Commit `c5cde133` hat den vorhandenen PowerShell-Live-Install geprüft. Er kompiliert kein Inno-Setup. `ISCC.exe` ist auf diesem Host nicht vorhanden und wird nicht heruntergeladen.
