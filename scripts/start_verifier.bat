@echo off
echo Starting Courier Verifier...
cd /d "%~dp0\.."

set "PYTHON_EXE=python"
if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist "%~dp0..\.venv_service\Scripts\python.exe" set "PYTHON_EXE=.venv_service\Scripts\python.exe"

start /B cmd /c "%PYTHON_EXE% -u -m scripts.courier_verifier >> scripts\verifier.log 2>&1"
