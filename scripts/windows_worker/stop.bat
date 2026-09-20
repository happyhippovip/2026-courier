@echo off
echo Stopping Courier Windows Worker...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'daemon.py|run_loop.bat' } | Invoke-CimMethod -MethodName Terminate | Out-Null"
echo Stopped.
