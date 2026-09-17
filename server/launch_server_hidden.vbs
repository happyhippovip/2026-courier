Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\lol\2026-workspace\courier"
WshShell.Run """C:\Users\lol\2026-workspace\courier\.venv_service\Scripts\pythonw.exe"" server\run_waitress.py", 0, False
Set WshShell = Nothing
