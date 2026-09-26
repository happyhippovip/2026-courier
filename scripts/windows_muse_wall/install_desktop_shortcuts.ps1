#Requires -Version 5.1
<#
  Desktop installer for the Muse Auto starter trio. Idempotent.

  Creates on the current user's Desktop:
  - "Muse 16 Auto"  -> launch_32_auto.ps1 -Target 16
  - "Muse 32 Auto"  -> launch_32_auto.ps1 -Target 32 (STANDARD)
  - "Muse 64 Auto"  -> launch_32_auto.ps1 -Target 64 (gated: runs only when
    stage 32 PASS is already proven; 64 is never forced)
  - "Muse 32 YOLO"  -> launch_32_auto.ps1 -Target 32 -Yolo (ONLY when THIS
    machine's fresh probe proves --yolo is listed in `muse --help`;
    otherwise skipped)

  Preservation contract:
  - "Muse Original" is NEVER created, modified, moved, or deleted here.
    If it is missing, warn only (its target is unknown to this repo).
  - Only the trio files above (+ conditional YOLO) are written. No
    broad process-name kills, no credential, profile, ACL, or sandbox
    changes. No Google/Antigravity/P3 contact.
#>
param(
    [switch]$SkipProbe
)

$ErrorActionPreference = 'Stop'

$wallDir = $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $wallDir)

$desktop = [Environment]::GetFolderPath('Desktop')
if ([string]::IsNullOrWhiteSpace($desktop) -or -not (Test-Path $desktop)) {
    throw 'Desktop folder could not be resolved for the current user.'
}

$original = Join-Path $desktop 'Muse Original.lnk'
if (Test-Path $original) {
    Write-Output 'MUSE_ORIGINAL_PRESERVED=YES (untouched)'
} else {
    Write-Output 'MUSE_ORIGINAL_PRESERVED=UNKNOWN (no Muse Original.lnk on this Desktop; nothing created or removed)'
}

if (-not $SkipProbe) {
    & "$wallDir\probe_muse.ps1"
}
$yoloSupported = $false
$probePath = Join-Path $repoRoot 'runtime\muse_probe.json'
if (Test-Path $probePath) {
    try {
        $yoloSupported = [bool]((Get-Content -Raw -Path $probePath | ConvertFrom-Json).yolo_supported)
    } catch {
        $yoloSupported = $false
    }
}

$powershellExe = Join-Path ([Environment]::GetFolderPath('System')) 'WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path $powershellExe)) { $powershellExe = 'powershell.exe' }
$launcher = Join-Path $wallDir 'launch_32_auto.ps1'

function New-StarterShortcut([string]$name, [string]$arguments) {
    $path = Join-Path $desktop ("$name.lnk")
    $shell = New-Object -ComObject WScript.Shell
    try {
        $shortcut = $shell.CreateShortcut($path)
        $shortcut.TargetPath = $powershellExe
        $shortcut.Arguments = $arguments
        $shortcut.WorkingDirectory = $repoRoot
        $shortcut.WindowStyle = 1
        $shortcut.Description = "$name (Courier Windows Muse Wall)"
        $shortcut.Save()
    } finally {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell)
    }
    Write-Output ("SHORTCUT_WRITTEN={0}" -f $path)
}

New-StarterShortcut 'Muse 16 Auto' ("-NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Target 16" -f $launcher)
New-StarterShortcut 'Muse 32 Auto' ("-NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Target 32" -f $launcher)
New-StarterShortcut 'Muse 64 Auto' ("-NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Target 64" -f $launcher)

if ($yoloSupported) {
    New-StarterShortcut 'Muse 32 YOLO' ("-NoProfile -ExecutionPolicy Bypass -File `"{0}`" -Target 32 -Yolo" -f $launcher)
    Write-Output 'MUSE_32_YOLO_SHORTCUT=CREATED (probe proved --yolo)'
} else {
    Write-Output 'MUSE_32_YOLO_SHORTCUT=SKIPPED (this muse does not list --yolo; nothing created)'
}
