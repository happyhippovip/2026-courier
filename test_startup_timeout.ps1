param (
    [switch]$RunTests
)

Write-Host "--- COURIER WINDOWS STARTUP TIMEOUT TEST ---"

$exePath = "$PSScriptRoot\scripts\windows_worker\dist\Courier.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "Courier.exe not found! Please build it first."
    exit 1
}

function Run-Scenario {
    param (
        [string]$ScenarioName,
        [scriptblock]$SetupBlock,
        [string]$ExpectedState
    )
    
    $testHome = "$env:TEMP\courier_timeout_test_$(Get-Random)"
    if (Test-Path $testHome) { Remove-Item -Recurse -Force $testHome }
    New-Item -ItemType Directory -Force -Path $testHome | Out-Null
    
    $env:LOCALAPPDATA = $testHome
    $env:COURIER_API_KEY = ""
    $env:COURIER_VERIFIER_API_KEY = ""
    $courierHome = "$testHome\Courier"
    $logDir = "$courierHome\logs"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    
    & $SetupBlock -testHome $testHome -courierHome $courierHome
    
    Write-Host "`n[$ScenarioName]"
    $proc = Start-Process -FilePath $exePath -PassThru -WindowStyle Hidden
    
    # Wait for exit or maximum 90 seconds
    $proc.WaitForExit(90000)
    
    if (-not $proc.HasExited) {
        $proc.Kill()
        Write-Host "Test timed out entirely, killed proc."
    }
    
    $logFile = "$logDir\launcher.log"
    $actualState = "UNKNOWN"
    
    if (Test-Path $logFile) {
        $content = Get-Content $logFile
        foreach ($line in $content) {
            if ($line -match "Controller state: (READY|STARTING|FAILED|TIMEOUT)") {
                $actualState = $matches[1]
            }
        }
    }
    
    if ($actualState -eq $ExpectedState) {
        Write-Host "[PASS] Expected $ExpectedState and got $actualState" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Expected $ExpectedState but got $actualState" -ForegroundColor Red
    }
    
    Remove-Item -Recurse -Force $testHome
}

# 1. READY (Normal startup)
Run-Scenario -ScenarioName "READY - Normal Startup" -ExpectedState "READY" -SetupBlock {
    param($testHome, $courierHome)
    # Do nothing, normal boot should work.
}

# 2. FAILED (Controller exits immediately)
# We can simulate this by placing a broken python executable or breaking the controller script
# Wait, the controller script is bundled. We can't break it easily.
# But we can create a dummy python.exe in the dist folder that just exits 1.
# Oh, we shouldn't break the global dist. We can use COURIER_PYTHON_OVERRIDE if it existed, but it doesn't.
# Wait, let's create a temporary python file inside the workspace and alter the environment? No, CourierLauncher hardcodes the python.exe path to baseDir\python\python.exe.
# Let's temporarily rename the controller module in courier_core so it fails to import.
Run-Scenario -ScenarioName "FAILED - Controller Crash" -ExpectedState "FAILED" -SetupBlock {
    param($testHome, $courierHome)
    $servePy = "$PSScriptRoot\scripts\windows_worker\dist\courier_core\serve.py"
    $serveBak = "$PSScriptRoot\scripts\windows_worker\dist\courier_core\serve.bak"
    Rename-Item -Path $servePy -NewName "serve.bak" -Force
    Set-Content -Path $servePy -Value "raise Exception('Intentional crash')"
    
    # Register a job to restore it
    Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
        if (Test-Path $serveBak) {
            Remove-Item -Force $servePy
            Rename-Item -Path $serveBak -NewName "serve.py" -Force
        }
    }
}

# Restore the file manually just in case
$servePy = "$PSScriptRoot\scripts\windows_worker\dist\courier_core\serve.py"
$serveBak = "$PSScriptRoot\scripts\windows_worker\dist\courier_core\serve.bak"
if (Test-Path $serveBak) {
    Remove-Item -Force $servePy
    Rename-Item -Path $serveBak -NewName "serve.py" -Force
}

# 3. TIMEOUT (Controller hangs and doesn't bind or respond to health)
Run-Scenario -ScenarioName "TIMEOUT - Slow Startup" -ExpectedState "TIMEOUT" -SetupBlock {
    param($testHome, $courierHome)
    $servePy = "$PSScriptRoot\scripts\windows_worker\dist\courier_core\serve.py"
    $serveBak = "$PSScriptRoot\scripts\windows_worker\dist\courier_core\serve.bak"
    Rename-Item -Path $servePy -NewName "serve.bak" -Force
    Set-Content -Path $servePy -Value "import time`nwhile True:`n    time.sleep(10)"
}

if (Test-Path $serveBak) {
    Remove-Item -Force $servePy
    Rename-Item -Path $serveBak -NewName "serve.py" -Force
}

Write-Host "`nStartup Timeout Trace Complete." -ForegroundColor Cyan
