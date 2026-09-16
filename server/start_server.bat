@echo off
echo Starting Courier Server...
cd /d "%~dp0\.."

set UV_PROJECT_ENVIRONMENT=%~dp0..\.venv_service
uv run --with flask python -m server.app >> server\server.log 2>&1
