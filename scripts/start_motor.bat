@echo off
echo Starting Courier Motor...
cd /d "%~dp0\.."

if not exist logs mkdir logs

set UV_PROJECT_ENVIRONMENT=%~dp0..\.venv_service

.venv_service\Scripts\python.exe -u scripts\start_motor.py
