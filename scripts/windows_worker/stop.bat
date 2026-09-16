@echo off
echo Stopping Courier Windows Worker...
schtasks /End /TN "CourierWindowsWorker" 2>NUL
if exist "%~dp0daemon.pid" (
    for /f "usebackq tokens=*" %%p in ("%~dp0daemon.pid") do (
        taskkill /F /T /PID %%p 2>NUL
    )
    del "%~dp0daemon.pid" 2>NUL
)
echo Stopped.
