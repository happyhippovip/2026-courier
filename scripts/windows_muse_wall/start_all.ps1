param(
    [ValidateSet(1, 4, 8, 16, 32, 64)][int]$Slots = 64,
    # Passed through to muse_wall_launcher.ps1. MUST stay empty until the
    # real Muse CLI command is verified on the machine (MUSE_YOLO_UNKNOWN).
    [string]$SlotCommand = ''
)
$ErrorActionPreference = 'Stop'

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$python = "$repoRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw 'Project virtual environment is required.' }
Set-Location $repoRoot

# Initialize supervisor against the canonical repo-root runtime (runtime/slots).
& $python -m scripts.windows_muse_wall.supervisor init --root $repoRoot

# Launch the visual wall with the same staged slot count.
& "$scriptDir\muse_wall_launcher.ps1" -Slots $Slots -SlotCommand $SlotCommand
