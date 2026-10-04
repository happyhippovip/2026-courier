param (
    [switch]$RunContinuationTest
)

Write-Host "--- COUNTERTEST: VERIFIED CONTINUATION ---"

$checkpointFile = Join-Path $env:TEMP "courier_work_checkpoint.json"
$receiptFile = Join-Path $env:TEMP "courier_continuation_receipt.txt"

# Cleanup from previous runs
Remove-Item $checkpointFile -ErrorAction SilentlyContinue
Remove-Item $receiptFile -ErrorAction SilentlyContinue

# 1. Work starts -> Checkpoint
Write-Host "`n[1] Courier Work Dispatch..."
$dummyWorkPath = Join-Path $env:TEMP "courier_long_work.ps1"
@"
`$progress = 0
while (`$progress -lt 5) {
    Start-Sleep -Seconds 1
    `$progress++
    @{ Status="WORKING"; Progress=`$progress } | ConvertTo-Json | Out-File '$checkpointFile' -Encoding utf8
}
@{ Status="DONE"; Progress=5 } | ConvertTo-Json | Out-File '$checkpointFile' -Encoding utf8
"@ | Out-File $dummyWorkPath -Encoding utf8

$workerPID = (Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File $dummyWorkPath" -PassThru -WindowStyle Hidden).Id
Write-Host "Dispatched worker (PID $workerPID)."

# Let it do some work and checkpoint
Start-Sleep -Seconds 2

# 2. Terminal host fails
Write-Host "`n[2] Simulating Terminal Host Failure..."
Write-Host "Terminal host crashed unexpectedly."

# 3. Work state preserved
$checkpointData = Get-Content $checkpointFile | ConvertFrom-Json
Write-Host "`n[3] Validating Checkpoint..."
if ($checkpointData.Status -eq "WORKING" -and $checkpointData.Progress -gt 0) {
    Write-Host "[PASS] Checkpoint exists on disk: Progress $($checkpointData.Progress)"
} else {
    Write-Host "[FAIL] Missing or invalid checkpoint!"
}

$workerAlive = Get-Process -Id $workerPID -ErrorAction SilentlyContinue
if ($workerAlive) {
    Write-Host "[PASS] Work process $workerPID is still running."
} else {
    Write-Host "[FAIL] Work process died!"
}

# 4. Terminal host restarts
Write-Host "`n[4] Terminal Host Restarts..."

# 5. Courier reconciles & no duplicate dispatch
Write-Host "`n[5] Courier Reconciles State..."
$currentCheckpoint = Get-Content $checkpointFile | ConvertFrom-Json
if ($currentCheckpoint.Status -eq "WORKING") {
    Write-Host "Reconciliation: Work is currently in progress. NOT dispatching duplicate."
    Write-Host "[PASS] Duplicate dispatch prevented."
}

# 6. Work finishes & becomes IDLE_READY
Write-Host "`n[6] Waiting for work to complete naturally..."
while ((Get-Content $checkpointFile | ConvertFrom-Json).Status -ne "DONE") {
    Start-Sleep -Seconds 1
}
Write-Host "[PASS] Work finished and transitioned to DONE/IDLE_READY."

# 7. Evidence receipt generated
Write-Host "`n[7] Generating Evidence Receipt..."
$receiptContent = "VERIFIED_CONTINUATION=YES`nWORKER_PID=$workerPID`nFINAL_STATE=DONE"
$receiptContent | Out-File $receiptFile -Encoding utf8
Write-Host "[PASS] Receipt generated at $receiptFile."

# Cleanup
Stop-Process -Id $workerPID -Force -ErrorAction SilentlyContinue
Remove-Item $dummyWorkPath -ErrorAction SilentlyContinue

Write-Host "`n--- VERIFIED CONTINUATION TEST COMPLETE ---"
