@echo off
setlocal

if exist "%~dp0.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)
if exist "%~dp0..\deploy\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0..\deploy\.env") do (
        if not "%%A"=="" set "%%A=%%B"
    )
)

if not defined COURIER_SERVER set "COURIER_SERVER=http://127.0.0.1:8080"

curl -s -H "Authorization: Bearer %COURIER_API_KEY%" %COURIER_SERVER%/status
