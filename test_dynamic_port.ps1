$ErrorActionPreference = "Stop"

# 1. Occupy default port 8080
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8080)
$listener.Start()
Write-Host "Occupied port 8080"

try {
    # 2. Build the package
    Write-Host "Building package..."
    .\scripts\windows_worker\build_package.ps1
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }

    # Clear logs
    $homeDir = "$env:LOCALAPPDATA\Courier"
    if (Test-Path "$homeDir\logs") {
        Remove-Item -Recurse -Force "$homeDir\logs\*"
    }

    # 3. Launch Courier
    Write-Host "Launching Courier..."
    $proc = Start-Process -FilePath ".\scripts\windows_worker\dist\Courier.exe" -PassThru
    $pid_val = $proc.Id

    # Wait for controller to start
    Start-Sleep -Seconds 5

    # 4. Discover assigned port
    $logFile = "$homeDir\logs\controller.log"
    if (-not (Test-Path $logFile)) {
        throw "controller.log not found!"
    }

    $port = $null
    $content = Get-Content $logFile
    foreach ($line in $content) {
        if ($line -match "controller listening on 127\.0\.0\.1:(\d+)") {
            $port = $matches[1]
            break
        }
    }

    if (-not $port) {
        throw "Could not discover dynamic port from logs! Logs:`n" + ($content -join "`n")
    }

    Write-Host "Discovered assigned port: $port"

    if ($port -eq 8080) {
        throw "Courier still bound to 8080 even though it was occupied!"
    }

    # 5. Health succeeds
    Write-Host "Testing health endpoint on port $port..."
    $token = (Get-Content "$homeDir\run\controller.token" -Raw).Trim()
    $headers = @{ "X-Courier-Token" = $token }

    $healthRes = Invoke-RestMethod -Uri "http://127.0.0.1:$port/v1/health" -Headers $headers -Method Get
    Write-Host "Health check response: $($healthRes | ConvertTo-Json -Compress)"
    if (-not $healthRes.mode) {
        throw "Health check failed!"
    }

    # 6. Shutdown succeeds
    Write-Host "Sending shutdown request..."
    $shutdownRes = Invoke-RestMethod -Uri "http://127.0.0.1:$port/v1/shutdown" -Headers $headers -Method Post
    Write-Host "Shutdown response: $($shutdownRes | ConvertTo-Json -Compress)"
    if ($shutdownRes.status -ne "STOPPING") {
        throw "Shutdown request failed!"
    }

    # Wait for process to exit
    Write-Host "Waiting for process to exit..."
    for ($i = 0; $i -lt 10; $i++) {
        if ($proc.HasExited) {
            break
        }
        Start-Sleep -Seconds 1
    }

    if (-not $proc.HasExited) {
        Stop-Process -Id $pid_val -Force
        throw "Process did not exit cleanly!"
    }

    Write-Host "[PASS] Dynamic port test succeeded."
} finally {
    $listener.Stop()
    if ($proc -and (-not $proc.HasExited)) {
        Stop-Process -Id $proc.Id -Force
    }
}
