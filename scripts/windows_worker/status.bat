@echo off
tasklist /FI "IMAGENAME eq Courier.exe" | findstr /I /C:"Courier.exe"
if errorlevel 1 (
  echo Worker status not proven. Courier.exe is not listed.
  exit /b 1
)
echo Courier.exe is listed.
exit /b 0
