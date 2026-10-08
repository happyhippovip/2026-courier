@echo off
echo Stopping Courier Windows Worker...
taskkill /F /IM Courier.exe
if errorlevel 1 (
  echo Stop not proven. taskkill exited non-zero.
  exit /b 1
)
echo Stopped.
exit /b 0
