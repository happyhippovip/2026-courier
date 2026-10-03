@echo off
setlocal EnableDelayedExpansion
echo Stopping Courier Windows Worker...
cd /d "%~dp0"
if exist run\worker.lock (
    set /p COURIER_PID=<run\worker.lock
    if not "!COURIER_PID!"=="" (
        taskkill /F /PID !COURIER_PID! /T 2>NUL
    )
) else (
    echo run\worker.lock not found. Cannot determine Courier PID safely.
)
echo Stopped.
