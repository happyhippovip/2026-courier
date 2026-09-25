@echo off
rem Read-only: shows whether Antigravity, its language server and local UI are up.
rem  status.cmd --e2e  additionally sends one harmless agent request.
"%LOCALAPPDATA%\CourierAntigravity\venv\Scripts\python.exe" "%LOCALAPPDATA%\CourierAntigravity\app\supervisor.py" status %*
pause
