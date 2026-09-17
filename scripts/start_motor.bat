@echo off
echo Starting Courier Motor...
cd /d "%~dp0\.."

if not exist logs mkdir logs

set UV_PROJECT_ENVIRONMENT=%~dp0..\.venv_service

start /B cmd /c ".venv_service\Scripts\python.exe -u -m server.app >> logs\courier_daemon.log 2>&1"
start /B cmd /c ".venv_service\Scripts\python.exe -u -m scripts.courier_github_dispatcher >> logs\courier_github_dispatcher.log 2>&1"
start /B cmd /c ".venv_service\Scripts\python.exe -u -m scripts.courier_watchdog >> logs\courier_watchdog.log 2>&1"
