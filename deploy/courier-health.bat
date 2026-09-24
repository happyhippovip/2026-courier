@echo off
setlocal
if not defined COURIER_SERVER set "COURIER_SERVER=http://127.0.0.1:8080"
curl -s %COURIER_SERVER%/health
