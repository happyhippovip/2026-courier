@echo off
set "RUN_DIR=%LOCALAPPDATA%\Courier\run"
set "ANY_RUNNING=0"

if exist "%RUN_DIR%\launcher.pid" (
    for /f "usebackq tokens=*" %%P in ("%RUN_DIR%\launcher.pid") do (
        tasklist /FI "PID eq %%P" 2>NUL | findstr /I "%%P" >NUL
        if not errorlevel 1 (
            echo Launcher is RUNNING (PID %%P)
            set "ANY_RUNNING=1"
        )
    )
)

if exist "%RUN_DIR%\worker.pid" (
    for /f "usebackq tokens=*" %%P in ("%RUN_DIR%\worker.pid") do (
        tasklist /FI "PID eq %%P" 2>NUL | findstr /I "%%P" >NUL
        if not errorlevel 1 (
            echo Worker is RUNNING (PID %%P)
            set "ANY_RUNNING=1"
        )
    )
)

if exist "%RUN_DIR%\controller.pid" (
    for /f "usebackq tokens=*" %%P in ("%RUN_DIR%\controller.pid") do (
        tasklist /FI "PID eq %%P" 2>NUL | findstr /I "%%P" >NUL
        if not errorlevel 1 (
            echo Controller is RUNNING (PID %%P)
            set "ANY_RUNNING=1"
        )
    )
)

if exist "%RUN_DIR%\hub.pid" (
    for /f "usebackq tokens=*" %%P in ("%RUN_DIR%\hub.pid") do (
        tasklist /FI "PID eq %%P" 2>NUL | findstr /I "%%P" >NUL
        if not errorlevel 1 (
            echo Hub is RUNNING (PID %%P)
            set "ANY_RUNNING=1"
        )
    )
)

if "%ANY_RUNNING%"=="0" (
    tasklist /FI "IMAGENAME eq Courier.exe" 2>NUL | findstr /I "Courier.exe" >NUL
    if not errorlevel 1 (
        echo Courier Symphony is RUNNING:
        tasklist /FI "IMAGENAME eq Courier.exe"
    ) else (
        echo Courier Symphony is NOT running.
    )
)
