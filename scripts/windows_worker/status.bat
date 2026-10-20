@echo off
if exist "%LOCALAPPDATA%\Courier\worker.pid" (
    set /p PID=<"%LOCALAPPDATA%\Courier\worker.pid"
    tasklist /FI "PID eq %PID%" | findstr /I "Courier.exe" >NUL
    if not ERRORLEVEL 1 (
        echo Courier Windows Worker IS running ^(PID %PID%^).
        goto :EOF
    )
)

if not exist "%~dp0worker.pid" goto check_exe

set /p PID=<"%~dp0worker.pid"
tasklist /FI "PID eq %PID%" | findstr /I "Courier.exe" >NUL
if ERRORLEVEL 1 (
    echo Fallback worker is NOT running.
) else (
    echo Fallback worker IS running ^(PID %PID%^).
)
goto :EOF

:check_exe
tasklist | findstr /I "Courier.exe" >NUL
if ERRORLEVEL 1 (
    echo Courier Windows Worker Service is NOT running.
) else (
    echo Courier Windows Worker Service IS running.
)

