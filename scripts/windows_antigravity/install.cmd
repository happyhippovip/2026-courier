@echo off
rem One-time setup: registers the single Antigravity startup/recovery authority.
rem Safe to run again at any time (idempotent). No admin rights needed.
setlocal
set "HERE=%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY where uv >nul 2>nul && set "PY=uv run --no-project python"
if not defined PY (
  echo INSTALL=NO ^(no Python found: install Python 3 or uv^)
  pause
  exit /b 2
)
%PY% "%HERE%supervisor.py" install %*
set "RC=%ERRORLEVEL%"
echo.
"%LOCALAPPDATA%\CourierAntigravity\venv\Scripts\python.exe" "%LOCALAPPDATA%\CourierAntigravity\app\supervisor.py" status
timeout /t 20 >nul
exit /b %RC%
