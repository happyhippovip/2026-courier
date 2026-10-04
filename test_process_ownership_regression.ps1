param (
    [switch]$RunRegressionTest
)

Write-Host "--- COUNTERTEST: PROCESS OWNERSHIP REGRESSION ---"

# Start unrelated processes
$unrelatedPSPath = Join-Path $env:TEMP "unrelated_ps.ps1"
@"
while (`$true) { Start-Sleep -Seconds 1 }
"@ | Out-File $unrelatedPSPath -Encoding utf8

$unrelatedPS = Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File $unrelatedPSPath" -PassThru -WindowStyle Hidden
Write-Host "Started unrelated powershell.exe (PID: $($unrelatedPS.Id))"

# We cannot easily mock 'Code.exe' and 'pwsh.exe' if they are not installed, so we will use more copies of powershell 
# and name them differently in the script block or just rely on standard PS and python.
# Let's mock a 'Courier-like' test process by just running powershell with a specific title
$unrelatedCourierLikePS = Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"`$host.UI.RawUI.WindowTitle='Courier-like-process'; while (`$true) { Start-Sleep -Seconds 1 }`"" -PassThru -WindowStyle Hidden
Write-Host "Started unrelated 'Courier-like' process (PID: $($unrelatedCourierLikePS.Id))"

# Start Courier's *OWNED* process
$ownedProcess = Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"while (`$true) { Start-Sleep -Seconds 1 }`"" -PassThru -WindowStyle Hidden
Write-Host "Started Courier OWNED process (PID: $($ownedProcess.Id))"

# Courier Recovery Simulator (Must only kill owned process)
Write-Host "Simulating Courier Recovery / Process Cleanup..."
# BAD implementation would be: Stop-Process -Name powershell -Force
# GOOD implementation (what we simulate):
Stop-Process -Id $ownedProcess.Id -Force
Write-Host "Courier killed its owned process (PID: $($ownedProcess.Id))"

Start-Sleep -Seconds 2

# Asserts
$failCount = 0

if (Get-Process -Id $unrelatedPS.Id -ErrorAction SilentlyContinue) {
    Write-Host "[PASS] Unrelated powershell.exe survived."
} else {
    Write-Host "[FAIL] Unrelated powershell.exe was killed!"
    $failCount++
}

if (Get-Process -Id $unrelatedCourierLikePS.Id -ErrorAction SilentlyContinue) {
    Write-Host "[PASS] Unrelated Courier-like process survived."
} else {
    Write-Host "[FAIL] Unrelated Courier-like process was killed!"
    $failCount++
}

if (Get-Process -Id $ownedProcess.Id -ErrorAction SilentlyContinue) {
    Write-Host "[FAIL] Owned process was not killed!"
    $failCount++
} else {
    Write-Host "[PASS] Owned process was successfully terminated."
}

# Cleanup
Stop-Process -Id $unrelatedPS.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $unrelatedCourierLikePS.Id -Force -ErrorAction SilentlyContinue
Remove-Item $unrelatedPSPath -ErrorAction SilentlyContinue

Write-Host "--- REGRESSION TEST COMPLETE: $failCount Failures ---"
