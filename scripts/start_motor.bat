@echo off
setlocal
echo Starting Courier Motor...
cd /d "%~dp0\.."

if not exist logs mkdir logs

set "REPO_ROOT=%~dp0.."
set "PYTHON_EXE="

if defined COURIER_PYTHON (
    if exist "%COURIER_PYTHON%" (
        set "PYTHON_EXE=%COURIER_PYTHON%"
        goto :found_python
    )
)

if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
        "%VIRTUAL_ENV%\Scripts\python.exe" -c "import flask, requests, psutil" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%VIRTUAL_ENV%\Scripts\python.exe"
            goto :found_python
        )
    )
)

if exist "%REPO_ROOT%\.venv_service\Scripts\python.exe" (
    "%REPO_ROOT%\.venv_service\Scripts\python.exe" -c "import flask, requests, psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=%REPO_ROOT%\.venv_service\Scripts\python.exe"
        goto :found_python
    )
)

if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    "%REPO_ROOT%\.venv\Scripts\python.exe" -c "import flask, requests, psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"
        goto :found_python
    )
)

if exist "C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe" (
    "C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe" -c "import flask, requests, psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe"
        goto :found_python
    )
)

if exist "C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe" (
    "C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe" -c "import flask, requests, psutil" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe"
        goto :found_python
    )
)

set "PYTHON_EXE=python"

:found_python
if "%COURIER_MOTOR_DRY_RUN%"=="1" (
    echo PYTHON_EXE=%PYTHON_EXE%
    exit /b 0
)

start /B cmd /c ""%PYTHON_EXE%" -u -m server.app >> logs\courier_daemon.log 2>&1"
start /B cmd /c ""%PYTHON_EXE%" -u -m scripts.courier_github_dispatcher >> logs\courier_github_dispatcher.log 2>&1"
start /B cmd /c ""%PYTHON_EXE%" -u -m scripts.courier_watchdog >> logs\courier_watchdog.log 2>&1"
