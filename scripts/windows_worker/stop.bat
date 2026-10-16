@echo off
echo Stopping Courier Windows Worker...
schtasks /End /TN "CourierWindowsWorker" 2>NUL
for %%F in (worker.pid launcher.pid controller.pid hub.pid) do (
    if exist "%LOCALAPPDATA%\Courier\run\%%F" (
        for /f "usebackq tokens=*" %%P in ("%LOCALAPPDATA%\Courier\run\%%F") do (
            taskkill /PID %%P /T /F 2>NUL
        )
        del "%LOCALAPPDATA%\Courier\run\%%F" 2>NUL
    )
)
echo Stopped.
