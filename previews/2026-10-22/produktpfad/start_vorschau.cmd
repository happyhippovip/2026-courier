@echo off
rem Startet die lokale Vorschau auf http://127.0.0.1:8766
cd /d "%~dp0"
py -3 -m http.server 8766 --bind 127.0.0.1 || python -m http.server 8766 --bind 127.0.0.1
