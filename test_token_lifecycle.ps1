param (
    [switch]$RunTests
)

Write-Host "--- COURIER WINDOWS TOKEN LIFECYCLE TEST ---"

$testHome = "$env:TEMP\courier_token_test_$(Get-Random)"
if (Test-Path $testHome) { Remove-Item -Recurse -Force $testHome }
New-Item -ItemType Directory -Force -Path $testHome | Out-Null

$env:LOCALAPPDATA = $testHome
$courierHome = "$testHome\Courier"
$runDir = "$courierHome\run"
$tokenFile = "$runDir\controller.token"

$exePath = "$PSScriptRoot\scripts\windows_worker\dist\Courier.exe"
if (-not (Test-Path $exePath)) {
    $exePath = "$PSScriptRoot\scripts\windows_worker\Courier.exe"
}

if (-not (Test-Path $exePath)) {
    Write-Error "Courier.exe not found! Please build it first."
    exit 1
}

function Run-Courier {
    $proc = Start-Process -FilePath $exePath -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 5 # Wait for initialization and controller boot
    return $proc
}

Write-Host "`n[1] Missing Token Test (Initial Boot)"
$proc1 = Run-Courier
if (Test-Path $tokenFile) {
    $token1 = (Get-Content $tokenFile -Raw).Trim()
    Write-Host "[PASS] Token was created: $token1" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Token file was not created!" -ForegroundColor Red
}
$proc1.Kill()
$proc1.WaitForExit()
Start-Sleep -Seconds 2

Write-Host "`n[2] Stale/Reused Token Test (Restart Behavior)"
$proc2 = Run-Courier
if (Test-Path $tokenFile) {
    $token2 = (Get-Content $tokenFile -Raw).Trim()
    if ($token1 -eq $token2) {
        Write-Host "[PASS] Token was correctly reused upon restart." -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Token was overwritten: $token2" -ForegroundColor Red
    }
}
$proc2.Kill()
$proc2.WaitForExit()
Start-Sleep -Seconds 2

Write-Host "`n[3] Pre-existing Wrong/Invalid Token Test"
# Serve.py demands >= 32 chars. Let's see if CourierLauncher or serve.py overwrites a short token.
Set-Content -Path $tokenFile -Value "short"
$proc3 = Run-Courier
$token3 = (Get-Content $tokenFile -Raw).Trim()
if ($token3 -ne "short") {
    Write-Host "[PASS] Short/invalid token was regenerated: $token3" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Short token was NOT regenerated!" -ForegroundColor Red
}
$proc3.Kill()
$proc3.WaitForExit()
Start-Sleep -Seconds 2

Write-Host "`n[4] Environment Variable Override Test"
Remove-Item -Force $tokenFile
$env:COURIER_API_KEY = "env-token-long-enough-to-pass-serve-py-validation-12345"
$proc4 = Run-Courier
$token4 = (Get-Content $tokenFile -Raw).Trim()
if ($token4 -eq "env-token-long-enough-to-pass-serve-py-validation-12345") {
    Write-Host "[PASS] Token was seeded from environment variable." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Token did not match environment variable: $token4" -ForegroundColor Red
}
$proc4.Kill()
$proc4.WaitForExit()
$env:COURIER_API_KEY = $null

Remove-Item -Recurse -Force $testHome
Write-Host "`nLifecycle Trace Complete." -ForegroundColor Cyan
