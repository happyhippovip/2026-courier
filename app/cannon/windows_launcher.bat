@echo off
REM Windows batch entry for Cannon launcher: exits after opening the ready URL.
setlocal
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%..\.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "app\cannon\windows_launcher.py"
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" "app\cannon\windows_launcher.py"
) else (
    python "app\cannon\windows_launcher.py"
)
popd
endlocal
