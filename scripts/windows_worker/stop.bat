@echo off
echo Stopping Courier Windows Worker...
if exist "%LOCALAPPDATA%\Courier\worker.pid" (
    set /p PID=<"%LOCALAPPDATA%\Courier\worker.pid"
    taskkill /F /T /PID %PID% 2>NUL
    del "%LOCALAPPDATA%\Courier\worker.pid" 2>NUL
)
if exist "%LOCALAPPDATA%\Courier\launcher.pid" (
    set /p LPID=<"%LOCALAPPDATA%\Courier\launcher.pid"
    taskkill /F /T /PID %LPID% 2>NUL
    del "%LOCALAPPDATA%\Courier\launcher.pid" 2>NUL
)
if exist "%~dp0worker.pid" (
    set /p PID=<"%~dp0worker.pid"
    taskkill /F /T /PID %PID% 2>NUL
    del "%~dp0worker.pid" 2>NUL
)
echo Stopped.

