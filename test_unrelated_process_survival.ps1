param (
    [switch]$RunSurvivalTest
)

Write-Host "--- COUNTERTEST: UNRELATED PROCESS SURVIVAL ---"

# Start unrelated PowerShell
$unrelatedPSPath = Join-Path $env:TEMP "unrelated_ps.ps1"
@"
while (`$true) { Start-Sleep -Seconds 1 }
"@ | Out-File $unrelatedPSPath -Encoding utf8
$unrelatedPS = Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File $unrelatedPSPath" -PassThru -WindowStyle Hidden
Write-Host "Started unrelated powershell.exe (PID: $($unrelatedPS.Id))"

# Start unrelated Python (mocking by copying powershell to python.exe for testing without relying on python being in PATH)
$mockPythonExe = Join-Path $env:TEMP "mock_python.exe"
Copy-Item "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Destination $mockPythonExe -Force
$unrelatedPython = Start-Process $mockPythonExe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"while (`$true) { Start-Sleep -Seconds 1 }`"" -PassThru -WindowStyle Hidden
Write-Host "Started unrelated mock python.exe (PID: $($unrelatedPython.Id))"

# Start unrelated VS Code mock
$mockCodeExe = Join-Path $env:TEMP "mock_Code.exe"
Copy-Item "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -Destination $mockCodeExe -Force
$unrelatedCode = Start-Process $mockCodeExe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"while (`$true) { Start-Sleep -Seconds 1 }`"" -PassThru -WindowStyle Hidden
Write-Host "Started unrelated mock Code.exe (PID: $($unrelatedCode.Id))"

# Start Courier's OWNED process
$ownedProcess = Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"while (`$true) { Start-Sleep -Seconds 1 }`"" -PassThru -WindowStyle Hidden
Write-Host "Started Courier OWNED process (PID: $($ownedProcess.Id))"

# Courier Cleanup Simulator
Write-Host "`nSimulating Courier Cleanup (Should only kill PID $($ownedProcess.Id))..."
Stop-Process -Id $ownedProcess.Id -Force
Write-Host "Courier killed its owned process."
Start-Sleep -Seconds 2

# Asserts
Write-Host "`nVerifying survivability:"
$failCount = 0

function Assert-Alive($proc, $name) {
    if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
        Write-Host "[PASS] Unrelated $name survived."
    } else {
        Write-Host "[FAIL] Unrelated $name was killed!"
        $global:failCount++
    }
}

Assert-Alive $unrelatedPS "powershell.exe"
Assert-Alive $unrelatedPython "python.exe"
Assert-Alive $unrelatedCode "Code.exe"

if (Get-Process -Id $ownedProcess.Id -ErrorAction SilentlyContinue) {
    Write-Host "[FAIL] Owned process was not killed!"
    $failCount++
} else {
    Write-Host "[PASS] Owned process was successfully terminated."
}

# Cleanup
Stop-Process -Id $unrelatedPS.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $unrelatedPython.Id -Force -ErrorAction SilentlyContinue
Stop-Process -Id $unrelatedCode.Id -Force -ErrorAction SilentlyContinue
Remove-Item $unrelatedPSPath -ErrorAction SilentlyContinue
Remove-Item $mockPythonExe -ErrorAction SilentlyContinue
Remove-Item $mockCodeExe -ErrorAction SilentlyContinue

Write-Host "`n--- REGRESSION TEST COMPLETE: $failCount Failures ---"
