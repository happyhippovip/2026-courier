# Requires Run as Administrator
$taskName = "CourierWindowsWorker"

Write-Host "========================================"
Write-Host " Courier Windows Worker Uninstaller"
Write-Host "========================================"

Write-Host "[1] Stopping Scheduled Task..."
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

Write-Host "[2] Unregistering Scheduled Task..."
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Write-Host "[3] Removing secure credentials from Windows Credential Manager..."
if (Get-Command "uv" -ErrorAction SilentlyContinue) {
    uv run --with keyring python -c "import keyring; keyring.delete_password('courier_worker', 'courier_api_key')" 2>$null
} else {
    Write-Host "WARNING: 'uv' not found. Cannot remove credentials automatically." -ForegroundColor Yellow
}

Write-Host "[4] Cleaning up running background processes..."
Stop-Process -Name "python" -ErrorAction SilentlyContinue

Write-Host "
[SUCCESS] Uninstallation complete!" -ForegroundColor Green
Write-Host "You can now safely delete the directory: $PSScriptRoot"
