param([Parameter(Mandatory=$true)][string]$Slot)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Project virtual environment is required.' }
& $python -m scripts.windows_muse_wall.supervisor stop --root $PSScriptRoot --slot $Slot
