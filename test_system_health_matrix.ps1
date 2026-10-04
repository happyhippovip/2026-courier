param (
    [switch]$RunTests
)

# Windows System Health Matrix Evaluator
# 
# Invariant enforced: CONTROL_PLANE_HEALTHY != SYSTEM_GUI_HEALTHY
# A background headless worker may be fully operational while the user's desktop is frozen.

$HealthMatrix = @{
    CONTROL_PLANE  = "UNKNOWN"
    SYSTEM_GUI     = "UNKNOWN"
    EXPLORER       = "UNKNOWN"
    DWM            = "UNKNOWN"
    TERMINAL_HOST  = "UNKNOWN"
    IDE            = "UNKNOWN"
    ANTIGRAVITY    = "UNKNOWN"
    BROWSER        = "UNKNOWN"
    COURIER_WORKER = "UNKNOWN"
}

function Evaluate-ProcessHealth {
    param([string]$ProcessName, [string]$Component)
    $procs = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    if (-not $procs) {
        $HealthMatrix[$Component] = "FAILED"
        return
    }
    
    # Check if any process is not responding (GUI lockup detection)
    $unresponsive = $procs | Where-Object { $_.MainWindowHandle -ne 0 -and $_.Responding -eq $false }
    if ($unresponsive) {
        $HealthMatrix[$Component] = "DEGRADED"
        return
    }
    
    $HealthMatrix[$Component] = "HEALTHY"
}

function Evaluate-HeadlessHealth {
    param([string]$Component, [scriptblock]$ProbeBlock)
    try {
        $healthy = & $ProbeBlock
        if ($healthy) {
            $HealthMatrix[$Component] = "HEALTHY"
        } else {
            $HealthMatrix[$Component] = "DEGRADED"
        }
    } catch {
        $HealthMatrix[$Component] = "FAILED"
    }
}

function Update-HealthMatrix {
    # 1. Evaluate GUI/Native Windows Layer
    Evaluate-ProcessHealth -ProcessName "explorer" -Component "EXPLORER"
    Evaluate-ProcessHealth -ProcessName "dwm" -Component "DWM"
    
    if ($HealthMatrix["EXPLORER"] -eq "DEGRADED" -or $HealthMatrix["DWM"] -eq "DEGRADED") {
        $HealthMatrix["SYSTEM_GUI"] = "DEGRADED"
    } elseif ($HealthMatrix["EXPLORER"] -eq "FAILED" -or $HealthMatrix["DWM"] -eq "FAILED") {
        $HealthMatrix["SYSTEM_GUI"] = "FAILED"
    } else {
        $HealthMatrix["SYSTEM_GUI"] = "HEALTHY"
    }

    # 2. Evaluate User Tools
    Evaluate-ProcessHealth -ProcessName "Code" -Component "IDE"
    Evaluate-ProcessHealth -ProcessName "msedge" -Component "BROWSER"
    Evaluate-ProcessHealth -ProcessName "antigravity" -Component "ANTIGRAVITY"

    # 3. Evaluate Terminal Host (e.g. PowerShell inside IDE)
    Evaluate-ProcessHealth -ProcessName "pwsh", "powershell" -Component "TERMINAL_HOST"

    # 4. Evaluate Courier Headless Layer
    # Worker process check
    Evaluate-ProcessHealth -ProcessName "Courier" -Component "COURIER_WORKER"
    
    # Control Plane API check
    Evaluate-HeadlessHealth -Component "CONTROL_PLANE" -ProbeBlock {
        # Mocking an API ping to local controller
        # In reality: Invoke-RestMethod http://127.0.0.1:8080/v1/health ...
        return $true
    }
}

function Print-Matrix {
    Write-Host "`n--- WINDOWS STRUCTURED HEALTH MATRIX ---"
    $HealthMatrix.GetEnumerator() | Sort-Object Name | Format-Table -Property Name, Value -AutoSize
    
    Write-Host "INVARIANT CHECK: CONTROL_PLANE vs SYSTEM_GUI"
    if ($HealthMatrix["CONTROL_PLANE"] -eq "HEALTHY" -and $HealthMatrix["SYSTEM_GUI"] -ne "HEALTHY") {
        Write-Host "[OK] Invariant maintained: Headless plane survived GUI failure." -ForegroundColor Green
    } elseif ($HealthMatrix["CONTROL_PLANE"] -eq $HealthMatrix["SYSTEM_GUI"]) {
        Write-Host "[OK] Symmetrical health state." -ForegroundColor Cyan
    } else {
        Write-Host "[!] Control plane failed while GUI is healthy." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------
# DETERMINISTIC SCENARIOS (TESTS)
# ---------------------------------------------------------

function Run-Scenario {
    param([string]$ScenarioName, [hashtable]$StateOverrides)
    Write-Host "`n>>> SCENARIO: $ScenarioName <<<" -ForegroundColor Magenta
    
    # Reset to baseline
    $global:HealthMatrix.Keys | ForEach-Object { $global:HealthMatrix[$_] = "HEALTHY" }
    
    # Apply overrides
    foreach ($key in $StateOverrides.Keys) {
        $global:HealthMatrix[$key] = $StateOverrides[$key]
    }
    
    Print-Matrix
}

if ($RunTests) {
    Run-Scenario -ScenarioName "Golden Path (All Systems Go)" -StateOverrides @{}
    
    Run-Scenario -ScenarioName "2026-10-02 Freeze (GUI Degraded, Agents Survive)" -StateOverrides @{
        EXPLORER = "DEGRADED"
        DWM = "DEGRADED"
        SYSTEM_GUI = "DEGRADED"
        IDE = "DEGRADED"
        TERMINAL_HOST = "FAILED"
        CONTROL_PLANE = "HEALTHY"
        COURIER_WORKER = "HEALTHY"
    }

    Run-Scenario -ScenarioName "Courier Outage (Worker Dead, GUI Fine)" -StateOverrides @{
        COURIER_WORKER = "FAILED"
        CONTROL_PLANE = "FAILED"
        SYSTEM_GUI = "HEALTHY"
        EXPLORER = "HEALTHY"
    }
} else {
    # Live Evaluation
    Update-HealthMatrix
    Print-Matrix
}
