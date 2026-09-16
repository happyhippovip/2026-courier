# Use HKCU Run to start server automatically
$taskName = "CourierServer"
$workingDir = Resolve-Path "$PSScriptRoot\.." | Select-Object -ExpandProperty Path
$pythonPath = "$workingDir\.venv_service\Scripts\python.exe"

Write-Host "Creating reproducible virtual environment for background service..."
Set-Location $workingDir
uv venv --allow-existing .venv_service
uv pip install --python .venv_service flask keyring waitress

$wrapperPath = "$PSScriptRoot\run_waitress.py"
$wrapperContent = @"
import sys, os, traceback
sys.path.insert(0, os.path.abspath('.'))
with open('server/crash.log', 'w') as f:
    sys.stdout = f
    sys.stderr = f
    try:
        import logging
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
        from waitress import serve
        from server import app
        f.write('Starting server...\n')
        f.flush()
        serve(app.app, host='0.0.0.0', port=8080)
    except BaseException as e:
        f.write(traceback.format_exc())
"@
Set-Content -Path $wrapperPath -Value $wrapperContent

# Create a small VBScript to launch pythonw.exe with the wrapper
$pythonwPath = "$workingDir\.venv_service\Scripts\pythonw.exe"
$vbsPath = "$PSScriptRoot\launch_server_hidden.vbs"
$vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$workingDir"
WshShell.Run """$pythonwPath"" server\run_waitress.py", 0, False
Set WshShell = Nothing
"@
Set-Content -Path $vbsPath -Value $vbsContent

New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $taskName -Value "wscript.exe `"$vbsPath`"" -PropertyType String -Force

Write-Host "Courier Server registered to start on boot via HKCU Run registry key."

# Also start it now so it escapes the current process job object and survives terminal exit
Invoke-WmiMethod -Class Win32_Process -Name Create -ArgumentList "wscript.exe `"$vbsPath`""
Write-Host "Courier Server started in background."
