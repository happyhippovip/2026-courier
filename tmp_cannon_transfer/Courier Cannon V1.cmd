@echo off
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app\server.py" --cannon-only --port 8768 --open
