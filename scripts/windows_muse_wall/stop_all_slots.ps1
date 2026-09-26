#Requires -Version 5.1
<#
  Exact-process stop for supervisor-tracked slot processes (MUSE-01..N).

  Calls supervisor stop once per slot: only the PID+create_time owned
  process is terminated; live foreign PIDs are never touched. No broad
  process-name kills, no window killing. Visual wt panes are closed by
  closing the wall window (one close); this script handles tracked job
  processes.
#>
param(
    [ValidateSet(1, 4, 8, 16, 32, 64)][int]$Slots = 32
)

$ErrorActionPreference = 'Stop'

$wallDir = $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $wallDir)
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Project virtual environment is required.' }
Set-Location $repoRoot

for ($i = 1; $i -le $Slots; $i++) {
    $slot = ('MUSE-{0:D2}' -f $i)
    $out = & $python -m scripts.windows_muse_wall.supervisor stop --root $repoRoot --slot $slot
    Write-Output ("{0}: {1}" -f $slot, $out)
    Start-Sleep -Milliseconds 200
}
