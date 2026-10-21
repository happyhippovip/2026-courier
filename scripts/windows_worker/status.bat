@echo off
python "%~dp0process_ownership.py" status 2>NUL
if %ERRORLEVEL% equ 0 exit /b 0
if exist "%LOCALAPPDATA%\Courier\worker.pid" (
    set /p PID=<"%LOCALAPPDATA%\Courier\worker.pid"
    set "NONNUM="
    for /f "delims=0123456789" %%a in ("%PID%") do set NONNUM=%%a
    if not defined NONNUM if defined PID (
        tasklist /FI "PID eq %PID%" | findstr /I "Courier.exe" >NUL
        if not ERRORLEVEL 1 (
            echo Courier Windows Worker IS running ^(PID %PID%^).
            goto :EOF
        )
    )
)

if not exist "%~dp0worker.pid" goto check_exe

set /p PID=<"%~dp0worker.pid"
set "NONNUM="
for /f "delims=0123456789" %%a in ("%PID%") do set NONNUM=%%a
if not defined NONNUM if defined PID (
    tasklist /FI "PID eq %PID%" | findstr /I "Courier.exe" >NUL
    if ERRORLEVEL 1 (
        echo Fallback worker is NOT running.
    ) else (
        echo Fallback worker IS running ^(PID %PID%^).
    )
    goto :EOF
)

:check_exe
tasklist | findstr /I "Courier.exe" >NUL
if ERRORLEVEL 1 (
    echo Courier Windows Worker Service is NOT running.
) else (
    echo Courier Windows Worker Service IS running.
)
