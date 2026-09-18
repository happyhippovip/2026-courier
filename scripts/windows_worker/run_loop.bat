@echo off
:loop
uv run python -u daemon.py >> logs\worker.log 2>&1
timeout /t 5 /nobreak >nul
goto loop
