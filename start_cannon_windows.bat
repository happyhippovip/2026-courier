@echo off
REM Cannon Ein-Klick-Start (Windows, Kunde) - Doppelklick-Einstieg im Repo-Root.
REM Setzt die Umgebungsvariablen und startet scripts\start_cannon_windows.ps1,
REM das den Motor im BEGRENZTEN local_fake-Modus startet:
REM Modus FINITE (BEGRENZT) + Limit, local_fake, kein echter Muse-Aufruf.
REM Aufruf: Doppelklick oder: cmd /c start_cannon_windows.bat
setlocal
cd /d "%~dp0"
if not defined COURIER_STATE_DIR set "COURIER_STATE_DIR=%USERPROFILE%\.courier\cannon-motor"
if not defined COURIER_LIMIT set "COURIER_LIMIT=3"
set "COURIER_RUN_MODE=local_fake"
set "COURIER_NO_NETWORK=1"
set "PYTHONIOENCODING=utf-8"
echo Cannon Ein-Klick-Start
echo   State-Dir : %COURIER_STATE_DIR%
echo   Modus     : FINITE (BEGRENZT), local_fake, Limit=%COURIER_LIMIT%
where python >nul 2>nul
if errorlevel 1 (
  echo CANNON_START=FAILED reason=no_python
  exit /b 3
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_cannon_windows.ps1" %*
if errorlevel 1 (
  echo CANNON_START=FAILED exit=%ERRORLEVEL%
  exit /b %ERRORLEVEL%
)
echo CANNON_START=OK
exit /b 0
