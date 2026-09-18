@echo off
echo Launching full Courier suite...

set COURIER_API_KEY=local-secret-key
set COURIER_VERIFIER_API_KEY=local-verifier-key

start "" /B cmd.exe /c ".\scripts\start_motor.bat"
start "" /B cmd.exe /c ".\scripts\start_verifier.bat"
start "" /B cmd.exe /c ".\scripts\windows_worker\start.bat"

echo All services started. Wait a few seconds for initialization.
