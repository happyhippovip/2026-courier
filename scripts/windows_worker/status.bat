@echo off
powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'daemon.py' } | Select-Object ProcessId, CommandLine"
