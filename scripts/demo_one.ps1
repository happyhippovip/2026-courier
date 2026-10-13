# Courier Ein-Befehl-Demo (MOCK) - Windows PowerShell
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
if (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 scripts/demo_one.py @args }
else { python scripts/demo_one.py @args }
exit $LASTEXITCODE
