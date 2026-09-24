@echo off
echo Starting Courier Motor...
cd /d "%~dp0\.."

if not exist logs mkdir logs

set "PYTHON_EXE=python"
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "%~dp0..\.venv_service\Scripts\python.exe" set "PYTHON_EXE=.venv_service\Scripts\python.exe"

start /B cmd /c "%PYTHON_EXE% -u -m server.app >> logs\courier_daemon.log 2>&1"
start /B cmd /c "%PYTHON_EXE% -u -m scripts.courier_github_dispatcher >> logs\courier_github_dispatcher.log 2>&1"
start /B cmd /c "%PYTHON_EXE% -u -m scripts.courier_watchdog >> logs\courier_watchdog.log 2>&1"
