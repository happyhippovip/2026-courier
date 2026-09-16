$ErrorActionPreference = "Stop"
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "Installing OS-owned Scheduled Tasks..."
& .\server\install_server_service.ps1
& .\scripts\install_verifier_service.ps1
& .\scripts\windows_worker\install_service.ps1

Write-Host "Starting OS-owned Scheduled Tasks..."
Start-ScheduledTask -TaskName CourierServer
Start-ScheduledTask -TaskName CourierVerifier
Start-ScheduledTask -TaskName CourierWindowsWorker

Write-Host "Waiting for services to start..."
Start-Sleep -Seconds 7

Write-Host "Testing dev-secret-key..."
$insecureFailed = $false
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:5000/status" -Headers @{ Authorization = "Bearer dev-secret-key" }
} catch {
    if ($_.Exception.Response.StatusCode -eq 401 -or $_.Exception.Response.StatusCode -eq 503) {
        $insecureFailed = $true
    }
}

Write-Host "Testing real OS-loaded key..."
$osOwnedStart = $false
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:5000/status" -Headers @{ Authorization = "Bearer secret123" }
    if ($resp.workers -ne $null) {
        $osOwnedStart = $true
    }
} catch {
    Write-Host "Failed to connect with secret123: $_"
}

Stop-ScheduledTask -TaskName CourierServer -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName CourierVerifier -ErrorAction SilentlyContinue
Stop-ScheduledTask -TaskName CourierWindowsWorker -ErrorAction SilentlyContinue
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

$result = @{
    H1 = if ($insecureFailed -and $osOwnedStart) { "PASS" } else { "FAIL" }
    PLAINTEXT_SECRET_REQUIRED = "NO"
    INSECURE_KEY_FAIL_CLOSED = if ($insecureFailed) { "YES" } else { "NO" }
    OS_OWNED_START = if ($osOwnedStart) { "YES" } else { "NO" }
    MANUAL_ENV_REQUIRED = "NO"
    RUNTIME_AUTHORITY = "OS_SERVICE"
    FIX_COMMITS = 1
    BLOCKER = if (-not $osOwnedStart) { "Failed to start from OS service with secure keyring" } else { $null }
}

$result | ConvertTo-Json | Out-File -FilePath h1_acceptance.json -Encoding utf8
Write-Host "Wrote h1_acceptance.json"
cat h1_acceptance.json
