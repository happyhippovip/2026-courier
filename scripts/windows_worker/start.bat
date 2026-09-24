@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0logs" mkdir "%~dp0logs"

set "REPO_ROOT=%~dp0..\.."
set "PYTHONPATH=%REPO_ROOT%"

set "PYTHON_EXE="

if defined COURIER_PYTHON (
    if exist "%COURIER_PYTHON%" (
        set "PYTHON_EXE=%COURIER_PYTHON%"
        goto :found_python
    )
)

if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
        "%VIRTUAL_ENV%\Scripts\python.exe" -c "import psutil" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%VIRTUAL_ENV%\Scripts\python.exe"
            goto :found_python
        )
    )
)

if exist "%REPO_ROOT%\.venv_service\Scripts\python.exe" (
    "%REPO_ROOT%\.venv_service\Scripts\python.exe" -c "import psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=%REPO_ROOT%\.venv_service\Scripts\python.exe"
        goto :found_python
    )
)

if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    "%REPO_ROOT%\.venv\Scripts\python.exe" -c "import psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"
        goto :found_python
    )
)

if exist "C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe" (
    "C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe" -c "import psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe"
        goto :found_python
    )
)

if exist "C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe" (
    "C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe" -c "import psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe"
        goto :found_python
    )
)

set "PYTHON_EXE=python"

:found_python
if "%COURIER_WORKER_DRY_RUN%"=="1" (
    echo PYTHON_EXE=%PYTHON_EXE%
    echo DAEMON=%~dp0daemon.py
    exit /b 0
)

start /B cmd /c ""%PYTHON_EXE%" -u "%~dp0daemon.py" >> "%~dp0logs\worker.log" 2>&1"
