param (
    [switch]$KillProcesses
)

$taskName = "CourierVerifier"

Write-Host "========================================"
Write-Host " Courier Verifier Service Uninstaller"
Write-Host "========================================"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Write-Host "[1] Stopping Scheduled Task $taskName..."
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

    Write-Host "[2] Unregistering Scheduled Task $taskName..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[SUCCESS] Task $taskName unregistered."
} else {
    Write-Host "[INFO] Scheduled Task $taskName is not registered."
}

if ($KillProcesses) {
    Write-Host "[3] Terminating Courier Verifier processes..."
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match "scripts\.courier_verifier" -or
        $_.CommandLine -match "start_verifier\.bat"
    } | Invoke-CimMethod -MethodName Terminate | Out-Null
}

Write-Host "[SUCCESS] Courier Verifier uninstallation complete."
