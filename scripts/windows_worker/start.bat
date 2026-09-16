@echo off
echo Starting Courier Windows Worker...
cd /d "%~dp0"
uv run python daemon.py
