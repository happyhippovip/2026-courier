@echo off
rem Removes the Scheduled Task. --restore re-enables launchers install disabled.
rem Never touches Antigravity, the Google profile, or credentials.
"%LOCALAPPDATA%\CourierAntigravity\venv\Scripts\python.exe" "%LOCALAPPDATA%\CourierAntigravity\app\supervisor.py" uninstall %*
pause
