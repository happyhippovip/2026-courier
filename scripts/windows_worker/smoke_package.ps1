# PowerShell Windows Package Smoke and Integrity Verifier
# Courier Symphony - Hardened Mutation & Policy Verifier
param(
    [string]$PackageDir = "$PSScriptRoot\dist"
)

$ErrorActionPreference = "Stop"

Write-Host "Running Courier Package Smoke Verification on '$PackageDir'..."

if (-not (Test-Path -LiteralPath $PackageDir)) {
    Write-Error "CRITICAL: Package directory '$PackageDir' does not exist."
    exit 1
}

# 1. Required core binaries and scripts
$requiredFiles = @(
    "Courier.exe",
    "daemon.py",
    "bootstrap.ps1",
    "install.ps1",
    "uninstall.ps1",
    "courier_worker\host.py",
    "courier_worker\service.py",
    "adapters\local_shell.py",
    "scripts\resource_policy.py",
    "events\policies\resource_policy.json"
)

$missing = @()
$emptyFiles = @()

foreach ($relPath in $requiredFiles) {
    $fullPath = Join-Path $PackageDir $relPath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        $missing += $relPath
    } else {
        $item = Get-Item -LiteralPath $fullPath
        if ($item.Length -lt 10) {
            $emptyFiles += "$relPath (Size: $($item.Length) bytes)"
        }
    }
}

if ($missing.Count -gt 0) {
    Write-Error "SMOKE_FAIL: Missing required package files: $($missing -join ', ')"
    exit 1
}

if ($emptyFiles.Count -gt 0) {
    Write-Error "SMOKE_FAIL: Truncated or empty files detected: $($emptyFiles -join ', ')"
    exit 1
}

# 2. Resource policy integrity
$policyJson = Join-Path $PackageDir "events\policies\resource_policy.json"
try {
    $rawJson = Get-Content -LiteralPath $policyJson -Raw -Encoding UTF8
    $parsed = ConvertFrom-Json $rawJson
    if (-not $parsed) {
        Write-Error "SMOKE_FAIL: resource_policy.json could not be parsed."
        exit 1
    }
} catch {
    Write-Error "SMOKE_FAIL: resource_policy.json is corrupt: $_"
    exit 1
}

# 3. Security guards verification in local_shell adapter
$localShell = Join-Path $PackageDir "adapters\local_shell.py"
$localShellContent = Get-Content -LiteralPath $localShell -Raw -Encoding UTF8
if ($localShellContent -notmatch "x00|nul" -or $localShellContent -notmatch "FORBIDDEN_COMMAND_BASENAMES|command_blocklist|blocked") {
    Write-Error "SMOKE_FAIL: local_shell.py is missing NUL-byte or command blocklist defense."
    exit 1
}

# 4. Resource policy script verification
$policyScript = Join-Path $PackageDir "scripts\resource_policy.py"
$policyScriptContent = Get-Content -LiteralPath $policyScript -Raw -Encoding UTF8
if ($policyScriptContent -notmatch "UNKNOWN|CostGate|BLOCK") {
    Write-Error "SMOKE_FAIL: resource_policy.py is missing CostGate or UNKNOWN cost enforcement."
    exit 1
}

Write-Host "SMOKE_PASS: All package files, policy definitions, and security invariants verified."
exit 0
