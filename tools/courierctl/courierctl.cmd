@echo off
setlocal

if defined COURIER_PYTHON (
    if exist "%COURIER_PYTHON%" (
        set "PYTHON_EXE=%COURIER_PYTHON%"
        goto :run
    )
)

if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
        "%VIRTUAL_ENV%\Scripts\python.exe" -c "import requests" >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=%VIRTUAL_ENV%\Scripts\python.exe"
            goto :run
        )
    )
)

if exist "%~dp0..\..\.venv\Scripts\python.exe" (
    "%~dp0..\..\.venv\Scripts\python.exe" -c "import requests" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
        goto :run
    )
)

if exist "%~dp0..\..\.venv_service\Scripts\python.exe" (
    "%~dp0..\..\.venv_service\Scripts\python.exe" -c "import requests" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=%~dp0..\..\.venv_service\Scripts\python.exe"
        goto :run
    )
)

if exist "C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe" (
    "C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe" -c "import requests" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=C:\Users\lol\2026-workspace\2026-courier\.venv\Scripts\python.exe"
        goto :run
    )
)

if exist "C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe" (
    "C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe" -c "import requests" >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=C:\Users\lol\2026-workspace\courier\.venv\Scripts\python.exe"
        goto :run
    )
)

set "PYTHON_EXE=python"

:run
"%PYTHON_EXE%" "%~dp0courierctl.py" %*
