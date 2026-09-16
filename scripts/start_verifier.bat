@echo off
echo Starting Courier Verifier...
cd /d "%~dp0\.."
set PYTHONPATH=.
set UV_PROJECT_ENVIRONMENT=%~dp0..\.venv_service
uv run --with requests python scripts/courier_verifier.py >> scripts\verifier.log 2>&1
