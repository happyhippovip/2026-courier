param (
    [switch]$RunTests
)

Write-Host "--- SAFE_TO_REBOOT DECISION CONTRACT ---"

class RebootState {
    [bool] $HasUncommittedWork
    [bool] $HasUnpushedCommits
    [bool] $HasActiveOwnedWork
    [bool] $HasCheckpointState
    [bool] $HasOpenWrites
    [bool] $HasRecoveryArtifacts
    [bool] $HasResumePoint
}

function Get-RebootSafety {
    param([RebootState]$State)
    
    # 1. UNKNOWN
    # If we lack visibility into the resume point or checkpoint state, we can't prove safety.
    if (-not $State.HasCheckpointState -and $State.HasActiveOwnedWork) {
        return "UNKNOWN" 
    }

    # 2. NOT_SAFE_TO_REBOOT
    # We never reboot if there is mid-flight data loss risk.
    if ($State.HasOpenWrites) { return "NOT_SAFE_TO_REBOOT" }
    
    # We never reboot if there's active work that hasn't written a recovery artifact.
    if ($State.HasActiveOwnedWork -and -not $State.HasRecoveryArtifacts) { return "NOT_SAFE_TO_REBOOT" }
    
    # We never reboot if we have unpushed commits or uncommitted work that lacks a resume point.
    if (($State.HasUncommittedWork -or $State.HasUnpushedCommits) -and -not $State.HasResumePoint) { 
        return "NOT_SAFE_TO_REBOOT" 
    }

    # 3. SAFE_TO_REBOOT
    # If work is cleanly suspended, checkpointed, and fully recoverable upon restart.
    return "SAFE_TO_REBOOT"
}

function Run-GateTest {
    param([string]$Name, [string]$Expected, [RebootState]$State)
    
    $result = Get-RebootSafety -State $State
    $color = if ($result -eq $Expected) { "Green" } else { "Red" }
    
    Write-Host "`n[Check] $Name"
    Write-Host "   Expected: $Expected"
    Write-Host "   Actual  : $result" -ForegroundColor $color
    if ($result -ne $Expected) {
        throw "Acceptance Check Failed: $Name"
    }
}

if ($RunTests) {
    # ---------------------------------------------------------
    # POSITIVE TESTS (SAFE)
    # ---------------------------------------------------------
    Run-GateTest -Name "Idle Clean Machine" -Expected "SAFE_TO_REBOOT" -State ([RebootState]@{
        HasUncommittedWork = $false; HasUnpushedCommits = $false
        HasActiveOwnedWork = $false; HasCheckpointState = $true
        HasOpenWrites = $false; HasRecoveryArtifacts = $false; HasResumePoint = $true
    })

    Run-GateTest -Name "Suspended Work (Safe Checkpoint)" -Expected "SAFE_TO_REBOOT" -State ([RebootState]@{
        HasUncommittedWork = $true; HasUnpushedCommits = $true
        HasActiveOwnedWork = $false; HasCheckpointState = $true
        HasOpenWrites = $false; HasRecoveryArtifacts = $true; HasResumePoint = $true
    })

    # ---------------------------------------------------------
    # NEGATIVE TESTS (NOT SAFE)
    # ---------------------------------------------------------
    Run-GateTest -Name "Active Open Writes" -Expected "NOT_SAFE_TO_REBOOT" -State ([RebootState]@{
        HasUncommittedWork = $true; HasUnpushedCommits = $false
        HasActiveOwnedWork = $true; HasCheckpointState = $true
        HasOpenWrites = $true; HasRecoveryArtifacts = $true; HasResumePoint = $false
    })

    Run-GateTest -Name "Unpushed Commits without Resume Point" -Expected "NOT_SAFE_TO_REBOOT" -State ([RebootState]@{
        HasUncommittedWork = $false; HasUnpushedCommits = $true
        HasActiveOwnedWork = $false; HasCheckpointState = $true
        HasOpenWrites = $false; HasRecoveryArtifacts = $true; HasResumePoint = $false
    })

    Run-GateTest -Name "Active Work without Recovery Artifacts" -Expected "NOT_SAFE_TO_REBOOT" -State ([RebootState]@{
        HasUncommittedWork = $false; HasUnpushedCommits = $false
        HasActiveOwnedWork = $true; HasCheckpointState = $true
        HasOpenWrites = $false; HasRecoveryArtifacts = $false; HasResumePoint = $true
    })

    # ---------------------------------------------------------
    # UNKNOWN TESTS (DANGEROUS)
    # ---------------------------------------------------------
    Run-GateTest -Name "Active Work but Checkpoint State Lost" -Expected "UNKNOWN" -State ([RebootState]@{
        HasUncommittedWork = $false; HasUnpushedCommits = $false
        HasActiveOwnedWork = $true; HasCheckpointState = $false
        HasOpenWrites = $false; HasRecoveryArtifacts = $true; HasResumePoint = $true
    })
    
    Write-Host "`nCRITICAL RULE: Courier must never reboot automatically regardless of gate state. It must only signal readiness." -ForegroundColor Cyan
}
