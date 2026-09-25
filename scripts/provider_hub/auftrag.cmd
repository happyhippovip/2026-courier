@echo off
rem Doppelklick: einen Auftrag an den lokalen Provider-Hub geben (Google oder Muse).
cd /d "%~dp0\..\.."
".venv\Scripts\python.exe" -m scripts.provider_hub.hub ask
echo.
pause
