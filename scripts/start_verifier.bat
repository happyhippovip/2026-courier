@echo off
echo Starting Courier Verifier...
cd /d "%~dp0\.."

set UV_PROJECT_ENVIRONMENT=%~dp0..\.venv_service
uv run --with requests python -m scripts.courier_verifier >> scripts\verifier.log 2>&1
