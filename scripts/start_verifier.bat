@echo off
echo Starting Courier Verifier...
cd /d "%~dp0\.."
if not defined COURIER_VERIFIER_LOG set "COURIER_VERIFIER_LOG=%CD%\scripts\verifier.log"
if not defined COURIER_VERIFIER_API_KEY (echo [start_verifier] COURIER_VERIFIER_API_KEY not defined & exit /b 2)
set "UV_PROJECT_ENVIRONMENT=%CD%\.venv"
if defined PYTHONPATH (set "PYTHONPATH=%CD%\scripts;%PYTHONPATH%") else (set "PYTHONPATH=%CD%\scripts")
if not exist ".venv\Scripts\python.exe" (echo [start_verifier] interpreter missing & exit /b 3)
".venv\Scripts\python.exe" -u -m scripts.courier_verifier
exit /b %ERRORLEVEL%
