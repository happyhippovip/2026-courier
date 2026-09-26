@echo off
echo Stopping Courier Windows Worker...
if exist worker.pid (
    set /p WORKER_PID=<worker.pid
    taskkill /F /T /PID %WORKER_PID% 2>NUL
    del worker.pid
) else (
    echo No worker.pid found.
)
echo Stopped.
