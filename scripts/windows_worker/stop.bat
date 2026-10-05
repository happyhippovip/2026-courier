@echo off
echo Stopping Courier Windows Worker...
taskkill /F /IM Courier.exe 2>NUL
if not exist "%~dp0worker.pid" goto end
set /p PID=<"%~dp0worker.pid"
taskkill /F /T /PID %PID% 2>NUL
del "%~dp0worker.pid"
:end
echo Stopped.

