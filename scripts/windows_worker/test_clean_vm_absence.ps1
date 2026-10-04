param (
    [switch]$RunTests
)

Write-Host "--- CLEAN-VM INTEGRATION TEST ---"
Write-Host "Asserting uv and python are absent from the system PATH."

# Helper to check if a command exists in PATH
function Test-CommandExists {
    param ([string]$Command)
    $path = Get-Command $Command -ErrorAction SilentlyContinue
    if ($path) {
        return $true
    }
    return $false
}

$uvExists = Test-CommandExists "uv"
$pythonExists = Test-CommandExists "python"

if ($uvExists) {
    Write-Host "[FAIL] 'uv' was found in PATH. Clean-VM constraint violated." -ForegroundColor Red
} else {
    Write-Host "[PASS] 'uv' is absent from PATH." -ForegroundColor Green
}

if ($pythonExists) {
    Write-Host "[FAIL] 'python' was found in PATH. Clean-VM constraint violated." -ForegroundColor Red
} else {
    Write-Host "[PASS] 'python' is absent from PATH." -ForegroundColor Green
}

if ($uvExists -or $pythonExists) {
    # We don't exit 1 here normally unless strict mode, to allow dev environments, 
    # but in CI this should fail the gate.
    if ($env:CI_STRICT_MODE -eq "1") {
        Write-Error "Clean-VM constraints violated. Development tools found on system PATH."
        exit 1
    }
}

Write-Host "`nClean-VM assertions complete." -ForegroundColor Cyan
