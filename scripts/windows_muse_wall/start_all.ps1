$ErrorActionPreference = 'Stop'

$scriptDir = $PSScriptRoot
$python = "$scriptDir\..\..\.venv\Scripts\python.exe"

# Initialize supervisor
& $python -m scripts.windows_muse_wall.supervisor init --root $scriptDir

# Launch the visual wall
& "$scriptDir\muse_wall_launcher.ps1"
