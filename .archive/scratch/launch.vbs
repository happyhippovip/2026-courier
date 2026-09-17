Set
WshShell
=
CreateObject
WScript.Shell
WshShell.Run
cmd /c .\.venv_service\Scripts\python.exe -u -m server.app >> logs\courier_daemon.log 2>&1
0
