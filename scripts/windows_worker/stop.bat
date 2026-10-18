@echo off
rem Stops only this user's Courier launcher and its child processes, by the
rem PID the launcher recorded. Never by image name (see stop.ps1).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1" %*
exit /b %ERRORLEVEL%
