$ErrorActionPreference = "Stop"

Write-Host "--- BUNDLE ALLOWLIST TEST ---"

$BundlePath = "C:\Users\lol\2026-workspace\2026-courier\scripts\windows_worker\CourierWorker-v1.zip"
if (-not (Test-Path $BundlePath)) {
    Write-Host "Rebuilding bundle..."
    & "C:\Users\lol\2026-workspace\2026-courier\scripts\windows_worker\build_package.ps1"
}

$ExtractDir = "C:\Users\lol\2026-workspace\2026-courier\scripts\windows_worker\dist_allowlist_test"
if (Test-Path $ExtractDir) { Remove-Item -Recurse -Force $ExtractDir }
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
Expand-Archive -Path $BundlePath -DestinationPath $ExtractDir -Force

$foundDbFiles = @(Get-ChildItem -Path $ExtractDir -Recurse -Include *.db, *.sqlite)
$foundMuse = @(Get-ChildItem -Path $ExtractDir -Recurse -Include *muse* -Directory)
$foundState = @(Get-ChildItem -Path $ExtractDir -Recurse -Include *state* -Directory)

$hasError = $false

if ($foundDbFiles.Count -gt 0) {
    Write-Host "[FAIL] Found SQLite databases in the bundle!"
    foreach ($file in $foundDbFiles) { Write-Host "  $($file.FullName)" }
    $hasError = $true
} else {
    Write-Host "[PASS] No .db or .sqlite state files found in the bundle."
}

if ($foundMuse.Count -gt 0) {
    Write-Host "[FAIL] Found Muse sessions/state in the bundle!"
    foreach ($dir in $foundMuse) { Write-Host "  $($dir.FullName)" }
    $hasError = $true
} else {
    Write-Host "[PASS] No Muse sessions/state found in the bundle."
}

if ($foundState.Count -gt 0) {
    Write-Host "[FAIL] Found 'state' directory in the bundle!"
    foreach ($dir in $foundState) { Write-Host "  $($dir.FullName)" }
    $hasError = $true
} else {
    Write-Host "[PASS] No generic 'state' directory found in the bundle."
}

if ($hasError) { exit 1 } else { Write-Host "--- TEST COMPLETE ---"; exit 0 }
