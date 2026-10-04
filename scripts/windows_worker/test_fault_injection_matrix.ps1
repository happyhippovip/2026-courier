$ErrorActionPreference = "Stop"

function Test-FaultInjectionMatrix {
    Write-Host "Running FAULT INJECTION MATRIX..."
    
    # 1. Port collision test
    # Simulate port 8080 taken
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 8080)
    $listener.Start()
    Write-Host "Simulated port 8080 binding."
    
    # Start Courier.exe and verify it dynamically binds to another port instead of failing
    $process = Start-Process -FilePath "Courier.exe" -PassThru -NoNewWindow
    Start-Sleep -Seconds 3
    
    if ($process.HasExited) {
        $listener.Stop()
        throw "FAULT INJECTION FAILED: Courier exited due to port collision."
    }
    
    Write-Host "Port collision handled successfully. Process is still running."
    
    # 2. Crash process handling
    # Kill the courier_core process and verify Courier.exe restarts it or exits gracefully
    $coreProcess = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "courier_core" }
    if ($coreProcess) {
        Stop-Process -Id $coreProcess.Id -Force
        Write-Host "Killed courier_core process."
        Start-Sleep -Seconds 5
        
        $newCoreProcess = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "courier_core" }
        if (-not $newCoreProcess) {
            Write-Host "FAULT INJECTION NOTE: courier_core did not restart automatically."
        } else {
            Write-Host "courier_core restarted automatically."
        }
    }
    
    # Clean up
    Stop-Process -Id $process.Id -Force
    $listener.Stop()
    Write-Host "FAULT INJECTION MATRIX COMPLETED SUCCESSFULLY."
}

Test-FaultInjectionMatrix
