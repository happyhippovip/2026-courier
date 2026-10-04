param (
    [switch]$RunFingerprintTest
)

Write-Host "--- COUNTERTEST: FREEZE FINGERPRINT (VS_CODE_POWERSHELL_EXT_EXIT_MINUS_ONE) ---"

function Get-IncidentFingerprint {
    param (
        [Hashtable]$Evidence
    )
    
    # 1. Check Exit Code
    $isExitMinusOne = ($Evidence.ExitCode -eq -1)
    
    # 2. Check Process / Host
    $isPowerShell = ($Evidence.ProcessName -match "powershell\.exe" -or $Evidence.ProcessName -match "pwsh\.exe")
    $isVSCode = ($Evidence.ParentProcess -match "Code\.exe" -or $Evidence.ExtensionHostState -eq "Failed")
    
    # 3. Exclude full GUI freeze or generic Explorer crashes
    $isFullGuiFreeze = ($Evidence.ExplorerState -eq "Frozen" -or $Evidence.DWMState -eq "Crashed")
    
    if ($isFullGuiFreeze) {
        return "UNKNOWN_FULL_SYSTEM_FREEZE"
    }
    
    if ($isExitMinusOne -and $isPowerShell -and $isVSCode) {
        return "VS_CODE_POWERSHELL_EXT_EXIT_MINUS_ONE"
    }
    
    return "UNRELATED_ERROR"
}

# --- TEST 1: Same incident recognized ---
$evidence1 = @{
    ExitCode = -1
    ProcessName = "powershell.exe"
    ParentProcess = "Code.exe"
    ExtensionHostState = "Failed"
    ExplorerState = "Healthy"
}
$result1 = Get-IncidentFingerprint -Evidence $evidence1
Write-Host "`n[Scenario 1] Genuine VS Code Terminal Crash"
Write-Host "Expected: VS_CODE_POWERSHELL_EXT_EXIT_MINUS_ONE -> Actual: $result1"
if ($result1 -eq "VS_CODE_POWERSHELL_EXT_EXIT_MINUS_ONE") { Write-Host "[PASS]" } else { Write-Host "[FAIL]" }

# --- TEST 2: Unrelated terminal error rejected ---
$evidence2 = @{
    ExitCode = 1
    ProcessName = "powershell.exe"
    ParentProcess = "cmd.exe"
    ExtensionHostState = "Healthy"
    ExplorerState = "Healthy"
}
$result2 = Get-IncidentFingerprint -Evidence $evidence2
Write-Host "`n[Scenario 2] Generic script failure (Exit 1) outside VS Code"
Write-Host "Expected: UNRELATED_ERROR -> Actual: $result2"
if ($result2 -eq "UNRELATED_ERROR") { Write-Host "[PASS]" } else { Write-Host "[FAIL]" }

# --- TEST 3: Full GUI freeze rejected ---
$evidence3 = @{
    ExitCode = -1
    ProcessName = "powershell.exe"
    ParentProcess = "Code.exe"
    ExtensionHostState = "Failed"
    ExplorerState = "Frozen"
}
$result3 = Get-IncidentFingerprint -Evidence $evidence3
Write-Host "`n[Scenario 3] Full machine GUI freeze"
Write-Host "Expected: UNKNOWN_FULL_SYSTEM_FREEZE -> Actual: $result3"
if ($result3 -eq "UNKNOWN_FULL_SYSTEM_FREEZE") { Write-Host "[PASS]" } else { Write-Host "[FAIL]" }

Write-Host "`n--- FINGERPRINT TEST COMPLETE ---"
