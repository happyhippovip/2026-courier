@echo off
echo Starting Courier Server...
cd /d "%~dp0\.."
set PYTHONPATH=.
set UV_PROJECT_ENVIRONMENT=%~dp0..\.venv_service
uv run --with flask python server/app.py >> server\server.log 2>&1
