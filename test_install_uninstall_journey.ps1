$ErrorActionPreference = 'Stop'

Write-Host "Starting INSTALL_UNINSTALL_JOURNEY acceptance prep..."

$InstallScript = "scripts\windows_worker\install_courier.ps1"
$UninstallScript = "scripts\windows_worker\uninstall_courier.ps1"
$ZipPath = "scripts\windows_worker\CourierWorker-v1.zip"
$InstallDir = "$env:LOCALAPPDATA\Courier"
$StartupFolder = [Environment]::GetFolderPath('Startup')
$ShortcutPath = "$StartupFolder\Courier Worker.lnk"

# Ensure clean state
if (Test-Path $InstallDir) {
    Write-Host "Cleaning up old installation..."
    & $UninstallScript
}

Write-Host "--- Testing Installation ---"
& $InstallScript -ZipPath $ZipPath

Start-Sleep -Seconds 3

# Verify Installation
if (-not (Test-Path $InstallDir)) {
    Write-Error "InstallDir $InstallDir does not exist."
    exit 1
}

if (-not (Test-Path "$InstallDir\Courier.exe")) {
    Write-Error "Courier.exe not found in $InstallDir."
    exit 1
}

if (-not (Test-Path $ShortcutPath)) {
    Write-Error "Startup shortcut not found at $ShortcutPath."
    exit 1
}

$proc = Get-Process -Name "Courier" -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-Error "Courier.exe is not running after installation."
    exit 1
} else {
    Write-Host "Courier process is running (ID: $($proc.Id))."
}

Write-Host "--- Installation verified successfully ---"

Write-Host "--- Testing Uninstallation ---"
& $UninstallScript

Start-Sleep -Seconds 3

# Verify Uninstallation
$proc = Get-Process -Name "Courier" -ErrorAction SilentlyContinue
if ($proc) {
    Write-Error "Courier.exe is still running after uninstallation."
    exit 1
}

if (Test-Path $InstallDir) {
    Write-Error "InstallDir $InstallDir still exists after uninstallation."
    exit 1
}

if (Test-Path $ShortcutPath) {
    Write-Error "Startup shortcut still exists after uninstallation."
    exit 1
}

Write-Host "--- Uninstallation verified successfully ---"
Write-Host "INSTALL_UNINSTALL_JOURNEY PASSED"
