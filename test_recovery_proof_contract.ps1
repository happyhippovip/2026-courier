param (
    [switch]$RunTests
)

Write-Host "--- RECOVERY PROOF CONTRACT ---"

# ---------------------------------------------------------
# EVIDENCE DEFINITIONS
# ---------------------------------------------------------

class SystemEvidence {
    [bool] $AgentProcessAlive
    [bool] $AgentHeartbeatRecent
    [bool] $TerminalProcessAlive
    [bool] $TerminalInputAccepted
    [bool] $ExplorerResponding
    [bool] $DwmResponding
    [bool] $ElectronAppsResponding
}

# ---------------------------------------------------------
# CONTRACT EVALUATOR
# ---------------------------------------------------------

function Get-RecoveryClassification {
    param([SystemEvidence]$Ev)
    
    # 1. NOT_RECOVERED
    # The absolute baseline: the agent is dead or not communicating.
    if (-not $Ev.AgentProcessAlive -or -not $Ev.AgentHeartbeatRecent) {
        return "NOT_RECOVERED"
    }

    # 2. FULL_SYSTEM_RECOVERY
    # Requires proof across MULTIPLE surfaces, specifically the GUI and Terminal.
    $guiHealthy = $Ev.ExplorerResponding -and $Ev.DwmResponding -and $Ev.ElectronAppsResponding
    $terminalHealthy = $Ev.TerminalProcessAlive -and $Ev.TerminalInputAccepted
    
    if ($guiHealthy -and $terminalHealthy) {
        return "FULL_SYSTEM_RECOVERY"
    }

    # 3. PARTIAL_SYSTEM_RECOVERY
    # The agent is fine, and *either* the Terminal is working OR the GUI is working, but not both.
    if ($guiHealthy -or $terminalHealthy) {
        return "PARTIAL_SYSTEM_RECOVERY"
    }

    # 4. AGENT_ONLY_RECOVERY
    # The agent is the ONLY thing working. The entire host shell and terminal are dead/locked.
    return "AGENT_ONLY_RECOVERY"
}

# ---------------------------------------------------------
# ACCEPTANCE CHECKS
# ---------------------------------------------------------

function Run-AcceptanceCheck {
    param([string]$Name, [string]$Expected, [SystemEvidence]$Ev)
    
    $result = Get-RecoveryClassification -Ev $Ev
    $color = if ($result -eq $Expected) { "Green" } else { "Red" }
    
    Write-Host "[Check] $Name"
    Write-Host "   Expected: $Expected"
    Write-Host "   Actual  : $result" -ForegroundColor $color
    if ($result -ne $Expected) {
        throw "Acceptance Check Failed: $Name"
    }
}

if ($RunTests) {
    # Test 1: Full System Restore
    $evFull = [SystemEvidence]@{
        AgentProcessAlive = $true; AgentHeartbeatRecent = $true
        TerminalProcessAlive = $true; TerminalInputAccepted = $true
        ExplorerResponding = $true; DwmResponding = $true; ElectronAppsResponding = $true
    }
    Run-AcceptanceCheck -Name "Perfect Startup/Recovery" -Expected "FULL_SYSTEM_RECOVERY" -Ev $evFull

    # Test 2: The 2026-10-02 Freeze (Terminal Host dead, GUI dead)
    $evAgentOnly = [SystemEvidence]@{
        AgentProcessAlive = $true; AgentHeartbeatRecent = $true
        TerminalProcessAlive = $false; TerminalInputAccepted = $false
        ExplorerResponding = $false; DwmResponding = $false; ElectronAppsResponding = $false
    }
    Run-AcceptanceCheck -Name "GUI + Terminal Dead" -Expected "AGENT_ONLY_RECOVERY" -Ev $evAgentOnly

    # Test 3: Terminal Restarted, but GUI still locked
    $evPartial = [SystemEvidence]@{
        AgentProcessAlive = $true; AgentHeartbeatRecent = $true
        TerminalProcessAlive = $true; TerminalInputAccepted = $true
        ExplorerResponding = $false; DwmResponding = $true; ElectronAppsResponding = $false
    }
    Run-AcceptanceCheck -Name "Terminal Restored, Shell Dead" -Expected "PARTIAL_SYSTEM_RECOVERY" -Ev $evPartial
    
    # Test 4: Courier crashes
    $evNotRecovered = [SystemEvidence]@{
        AgentProcessAlive = $false; AgentHeartbeatRecent = $false
        TerminalProcessAlive = $true; TerminalInputAccepted = $true
        ExplorerResponding = $true; DwmResponding = $true; ElectronAppsResponding = $true
    }
    Run-AcceptanceCheck -Name "Courier Fatal Crash" -Expected "NOT_RECOVERED" -Ev $evNotRecovered

    Write-Host "`nAll acceptance checks passed." -ForegroundColor Cyan
}
