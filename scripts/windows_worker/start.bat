@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0logs" mkdir "%~dp0logs"

set "REPO_ROOT=%~dp0..\.."
set "PYTHONPATH=%REPO_ROOT%"

if exist "%REPO_ROOT%\.venv_service\Scripts\python.exe" (
    set "PYTHON_EXE=%REPO_ROOT%\.venv_service\Scripts\python.exe"
) else if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

if "%COURIER_WORKER_DRY_RUN%"=="1" (
    echo PYTHON_EXE=%PYTHON_EXE%
    echo DAEMON=%~dp0daemon.py
    exit /b 0
)

start /B cmd /c ""%PYTHON_EXE%" -u "%~dp0daemon.py" >> "%~dp0logs\worker.log" 2>&1"
