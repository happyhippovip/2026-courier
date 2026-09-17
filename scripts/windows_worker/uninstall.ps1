param (
    [switch]$RemoveData,
    [switch]$RemoveCredentials
)

# Requires Run as Administrator
$taskName = "CourierWindowsWorker"

Write-Host "========================================"
Write-Host " Courier Windows Worker Uninstaller"
Write-Host "========================================"

Write-Host "[1] Stopping Scheduled Task..."
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

Write-Host "[2] Unregistering Scheduled Task..."
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

if ($RemoveCredentials) {
    Write-Host "[3] Removing secure credentials from Windows Credential Manager..."
    if (Get-Command "uv" -ErrorAction SilentlyContinue) {
        uv run --with keyring python -c "import keyring; keyring.delete_password('courier_worker', 'courier_api_key')" 2>$null
    } else {
        Write-Host "WARNING: 'uv' not found. Cannot remove credentials automatically." -ForegroundColor Yellow
    }
} else {
    Write-Host "[3] Preserving secure credentials (use -RemoveCredentials to delete)."
}

Write-Host "[4] Cleaning up running background processes..."
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "daemon.py|start.bat" } | Invoke-CimMethod -MethodName Terminate | Out-Null

if ($RemoveData) {
    Write-Host "[5] Removing runtime and data files..."
    Remove-Item -Path $PSScriptRoot -Recurse -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "[5] Preserving directory data (use -RemoveData to delete)."
}

Write-Host "
[SUCCESS] Uninstallation complete!" -ForegroundColor Green
