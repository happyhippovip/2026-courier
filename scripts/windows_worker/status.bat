@echo off
echo Checking Courier Windows Worker status...
schtasks /Query /TN "CourierWindowsWorker" 2>NUL
if exist "%~dp0daemon.pid" (
    for /f "usebackq tokens=*" %%p in ("%~dp0daemon.pid") do (
        echo Worker PID: %%p
        tasklist /FI "PID eq %%p" 2>NUL
    )
) else (
    echo No active daemon.pid found.
)
