# PowerShell Windows Package Smoke and Integrity Verifier
# Courier Symphony - Hardened Mutation & Policy Verifier
param(
    [string]$PackageDir = "$PSScriptRoot\dist",
    [switch]$RequireManifest
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

# 2. Resource policy integrity & mandatory schema validation (W05 / GB-PKG-05)
$policyJson = Join-Path $PackageDir "events\policies\resource_policy.json"
try {
    $rawJson = Get-Content -LiteralPath $policyJson -Raw -Encoding UTF8
    $parsed = ConvertFrom-Json $rawJson
    if (-not $parsed) {
        Write-Error "SMOKE_FAIL: resource_policy.json could not be parsed."
        exit 1
    }
    # Enforce mandatory policy schema fields
    $hasVersion = ($null -ne $parsed.schema_version) -or ($null -ne $parsed.policy_version)
    if (-not $hasVersion) {
        Write-Error "SMOKE_FAIL: resource_policy.json is missing required version specification."
        exit 1
    }
    $hasInvariants = ($null -ne $parsed.operating_invariants) -or ($null -ne $parsed.max_spend)
    if (-not $hasInvariants) {
        Write-Error "SMOKE_FAIL: resource_policy.json is missing mandatory governance invariants."
        exit 1
    }
    if ($null -ne $parsed.operating_invariants) {
        if ($parsed.operating_invariants.require_human_gate_for_spend -ne $true) {
            Write-Error "SMOKE_FAIL: resource_policy.json violates spend invariant: require_human_gate_for_spend must be true."
            exit 1
        }
    }
    if ($null -ne $parsed.max_spend) {
        if ([double]$parsed.max_spend -gt 0.0) {
            Write-Error "SMOKE_FAIL: resource_policy.json violates autonomous spend limit: max_spend must be 0.00."
            exit 1
        }
    }
} catch {
    Write-Error "SMOKE_FAIL: resource_policy.json validation failed: $_"
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


# 5. Cryptographic Manifest & Hash Verification (W04 / GB-PKG-04)
$manifestPath = Join-Path $PackageDir "manifest.json"
if (Test-Path -LiteralPath $manifestPath) {
    try {
        $rawManifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
        $manifestObj = ConvertFrom-Json $rawManifest
        if (-not $manifestObj -or -not $manifestObj.files) {
            Write-Error "SMOKE_FAIL: manifest.json is invalid or missing 'files' dictionary."
            exit 1
        }
    } catch {
        Write-Error "SMOKE_FAIL: manifest.json is corrupt: $_"
        exit 1
    }

    $manifestFiles = $manifestObj.files
    $hashMismatches = @()
    $sizeMismatches = @()
    $missingFromDisk = @()

    foreach ($prop in $manifestFiles.PSObject.Properties) {
        $rel = $prop.Name
        $expected = $prop.Value
        $targetFile = Join-Path $PackageDir $rel

        if (-not (Test-Path -LiteralPath $targetFile)) {
            $missingFromDisk += $rel
            continue
        }

        $item = Get-Item -LiteralPath $targetFile
        if ($item.Length -ne $expected.size) {
            $sizeMismatches += "$rel (expected $($expected.size) bytes, got $($item.Length) bytes)"
        }

        $computedHash = (Get-FileHash -LiteralPath $targetFile -Algorithm SHA256).Hash.ToUpper()
        if ($computedHash -ne $expected.sha256.ToUpper()) {
            $hashMismatches += "$rel (hash mismatch: expected $($expected.sha256), got $computedHash)"
        }
    }

    if ($missingFromDisk.Count -gt 0) {
        Write-Error "SMOKE_FAIL: Files in manifest missing from disk: $($missingFromDisk -join ', ')"
        exit 1
    }
    if ($sizeMismatches.Count -gt 0) {
        Write-Error "SMOKE_FAIL: Manifest file size discrepancies: $($sizeMismatches -join ', ')"
        exit 1
    }
    if ($hashMismatches.Count -gt 0) {
        Write-Error "SMOKE_FAIL: Cryptographic checksum failures: $($hashMismatches -join ', ')"
        exit 1
    }
} elseif ($RequireManifest) {
    Write-Error "SMOKE_FAIL: Required manifest.json is missing in '$PackageDir'."
    exit 1
}

Write-Host "SMOKE_PASS: All package files, policy definitions, and security invariants verified."
exit 0
