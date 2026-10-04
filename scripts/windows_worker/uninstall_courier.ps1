# Uninstall Courier Worker

$installDir = "$env:LOCALAPPDATA\Courier"
Write-Host "Uninstalling Courier Worker..."

Write-Host "Stopping Courier..."
if (Test-Path "$installDir\run\launcher.pid") {
    $pidStr = Get-Content "$installDir\run\launcher.pid"
    try {
        Stop-Process -Id $pidStr -Force -ErrorAction SilentlyContinue
    } catch {}
}
Stop-Process -Name "Courier" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "Removing auto-start shortcut..."
$startupFolder = [Environment]::GetFolderPath('Startup')
$shortcutPath = "$startupFolder\Courier Worker.lnk"
if (Test-Path $shortcutPath) {
    Remove-Item -Force $shortcutPath
}

if (Test-Path $installDir) {
    Write-Host "Removing installation directory..."
    Remove-Item -Recurse -Force $installDir
}

Write-Host "Uninstallation complete."
