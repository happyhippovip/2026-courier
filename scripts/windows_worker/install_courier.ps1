param (
    [string]$ZipPath = "CourierWorker-v1.zip",
    [switch]$StartAfterInstall = $true
)

# Refuse to run as administrator
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "FATAL: Courier must be installed as a standard user. Do not run as Administrator." -ForegroundColor Red
    exit 3
}

$installDir = "$env:LOCALAPPDATA\Courier"
Write-Host "Installing Courier Worker to $installDir..."

if (-not (Test-Path $ZipPath)) {
    Write-Error "Could not find $ZipPath. Please provide the path to CourierWorker-v1.zip."
    exit 1
}

if (Test-Path $installDir) {
    Write-Host "Stopping existing Courier process if running..."
    if (Test-Path "$installDir\run\launcher.pid") {
        $pidStr = Get-Content "$installDir\run\launcher.pid"
        try {
            Stop-Process -Id $pidStr -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    Stop-Process -Name "Courier" -Force -ErrorAction SilentlyContinue
    
    # Wait for file locks to release
    Start-Sleep -Seconds 2
} else {
    New-Item -ItemType Directory -Force -Path $installDir | Out-Null
}

Write-Host "Extracting files..."
Expand-Archive -Path $ZipPath -DestinationPath $installDir -Force

Write-Host "Setting up auto-start..."
$WScriptShell = New-Object -ComObject WScript.Shell
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = "$startupFolder\Courier Worker.lnk"
$shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$installDir\Courier.exe"
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "Courier Agent Worker"
$shortcut.Save()

if ($StartAfterInstall) {
    Write-Host "Starting Courier Worker..."
    Start-Process -FilePath "$installDir\Courier.exe" -WorkingDirectory $installDir
}

Write-Host "Installation complete! Courier Worker is now running and will start automatically on login."
