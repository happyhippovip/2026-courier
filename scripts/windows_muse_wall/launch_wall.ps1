param([ValidateSet(1,4,8,16,32,64)][int]$Stage = 1)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Project virtual environment is required.' }
& $python -m scripts.windows_muse_wall.supervisor init --root $PSScriptRoot
& $python -m scripts.windows_muse_wall.supervisor admit --root $PSScriptRoot --level $Stage
