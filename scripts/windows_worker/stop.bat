@echo off
echo Stopping Courier Windows Worker...
python "%~dp0process_ownership.py" stop 2>NUL
if %ERRORLEVEL% equ 0 (
    echo Stopped.
    exit /b 0
)
if exist "%LOCALAPPDATA%\Courier\worker.pid" (
    set /p PID=<"%LOCALAPPDATA%\Courier\worker.pid"
    set "NONNUM="
    for /f "delims=0123456789" %%a in ("%PID%") do set NONNUM=%%a
    if not defined NONNUM if defined PID (
        taskkill /F /T /PID %PID% 2>NUL
    )
    del "%LOCALAPPDATA%\Courier\worker.pid" 2>NUL
)
if exist "%LOCALAPPDATA%\Courier\launcher.pid" (
    set /p LPID=<"%LOCALAPPDATA%\Courier\launcher.pid"
    set "NONNUM="
    for /f "delims=0123456789" %%a in ("%LPID%") do set NONNUM=%%a
    if not defined NONNUM if defined LPID (
        taskkill /F /T /PID %LPID% 2>NUL
    )
    del "%LOCALAPPDATA%\Courier\launcher.pid" 2>NUL
)
if exist "%~dp0worker.pid" (
    set /p PID=<"%~dp0worker.pid"
    set "NONNUM="
    for /f "delims=0123456789" %%a in ("%PID%") do set NONNUM=%%a
    if not defined NONNUM if defined PID (
        taskkill /F /T /PID %PID% 2>NUL
    )
    del "%~dp0worker.pid" 2>NUL
)
echo Stopped.
