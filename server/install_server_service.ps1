# Use HKCU Run to start server automatically
$taskName = "CourierServer"
$workingDir = Resolve-Path "$PSScriptRoot\.." | Select-Object -ExpandProperty Path
$pythonwPath = "$workingDir\.venv_service\Scripts\pythonw.exe"

Write-Host "Creating reproducible virtual environment for background service..."
Set-Location $workingDir
uv venv .venv_service
uv pip install --python .venv_service flask keyring

# Create a small VBScript to launch pythonw.exe in the correct working directory
$vbsPath = "$PSScriptRoot\launch_server_hidden.vbs"
$vbsContent = "Set WshShell = CreateObject(`"WScript.Shell`")`nWshShell.CurrentDirectory = `"$workingDir`"`nWshShell.Run chr(34) & `"$pythonwPath`" & chr(34) & `" -m server.app`", 0, False`nSet WshShell = Nothing"
Set-Content -Path $vbsPath -Value $vbsContent

New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name $taskName -Value "wscript.exe `"$vbsPath`"" -PropertyType String -Force

Write-Host "Courier Server registered to start on boot via HKCU Run registry key."

# Also start it now so it survives terminal exit
Start-Process "wscript.exe" -ArgumentList "`"$vbsPath`""
Write-Host "Courier Server started in background."
