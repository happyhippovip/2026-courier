@echo off
cd /d "C:\Users\lol\2026-workspace\courier"

powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'courier_control_plane.py' } | Stop-Process -Force -ErrorAction SilentlyContinue"

start /B powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -Command "Start-Process 'uv' -ArgumentList 'run', 'python', 'scripts\courier_control_plane.py', '--daemon' -WindowStyle Hidden"
