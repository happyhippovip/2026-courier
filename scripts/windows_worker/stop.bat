@echo off
echo Stopping Courier Windows Worker...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq CourierWindowsWorker*" 2>NUL
echo Stopped.
