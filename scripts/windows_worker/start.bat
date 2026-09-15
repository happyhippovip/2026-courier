@echo off
echo Starting Courier Windows Worker...
cd /d "%~dp0"
python daemon.py
