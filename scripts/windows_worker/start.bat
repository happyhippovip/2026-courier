@echo off
echo Starting Courier Windows Worker...
cd /d "%~dp0"
if not exist "logs" mkdir "logs"
start /B cmd /c "uv run python -u daemon.py >> logs\worker.log 2>&1"
