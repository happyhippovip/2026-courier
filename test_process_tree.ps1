$ErrorActionPreference = "Stop"

Write-Host "--- COURIER WINDOWS PROCESS TREE TEST ---"

$testHome = Join-Path $env:TEMP "courier_tree_test_$([guid]::NewGuid().ToString().Substring(0,8))"
New-Item -ItemType Directory -Path $testHome | Out-Null
$env:COURIER_HOME = $testHome
$env:COURIER_WORKER_PORT = "0"
$env:COURIER_API_KEY = "tree_test_token_that_is_at_least_32_characters_long"

Write-Host "Building package..."
.\scripts\windows_worker\build_package.ps1
if ($LASTEXITCODE -ne 0) { throw "Build failed" }

$courierExe = Join-Path (Get-Location).Path "scripts\windows_worker\dist\Courier.exe"

$process = Start-Process -FilePath $courierExe -PassThru -NoNewWindow -RedirectStandardOutput "$testHome\out.log" -RedirectStandardError "$testHome\err.log"
$rootPid = $process.Id

Write-Host "Launched Courier with PID: $rootPid"
Start-Sleep -Seconds 5

function Get-ChildProcesses {
    param($parentId, $indent = "")
    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $parentId }
    foreach ($child in $children) {
        $cmd = $child.CommandLine
        if (-not $cmd) { $cmd = $child.Name }
        Write-Host "${indent}+-- PID: $($child.ProcessId) - $($child.Name) ($cmd)"
        Get-ChildProcesses -parentId $child.ProcessId -indent "$indent    "
    }
}

Write-Host "`nProcess Tree:"
Write-Host "PID: $rootPid - Courier.exe"
Get-ChildProcesses -parentId $rootPid

Write-Host "`nShutting down Courier..."
Stop-Process -Id $rootPid -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

if (Test-Path "$testHome\out.log") {
    Write-Host "`n--- OUT LOG ---"
    Get-Content "$testHome\out.log"
}
if (Test-Path "$testHome\err.log") {
    Write-Host "`n--- ERR LOG ---"
    Get-Content "$testHome\err.log"
}

# Cleanup any orphaned processes from the tree
$allChildren = @()
function Collect-ChildPids {
    param($parentId)
    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $parentId }
    foreach ($child in $children) {
        $allChildren += $child.ProcessId
        Collect-ChildPids -parentId $child.ProcessId
    }
}
Collect-ChildPids -parentId $rootPid
foreach ($pidToKill in $allChildren) {
    try {
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
    } catch {}
}

Remove-Item -Recurse -Force $testHome -ErrorAction SilentlyContinue

Write-Host "Process Tree Test Complete."
