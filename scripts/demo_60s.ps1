# Courier 60-Sekunden-Demo (MOCK) - Windows PowerShell
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:PYTHONIOENCODING = "utf-8"
if (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 scripts/demo_60s.py @args }
else { python scripts/demo_60s.py @args }
exit $LASTEXITCODE
