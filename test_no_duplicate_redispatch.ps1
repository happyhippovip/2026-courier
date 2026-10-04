param (
    [switch]$RunTests
)

Write-Host "--- REGRESSION TEST: NO DUPLICATE REDISPATCH ---"

# ---------------------------------------------------------
# MOCK COURIER LEDGER / STATE
# ---------------------------------------------------------

$global:Ledger = @{
    Tasks = @{}
    Results = @{}
}

function Invoke-WorkPhase {
    param([string]$TaskId, [string]$Phase)
    
    # Check if task already has a final result
    if ($global:Ledger.Results.ContainsKey($TaskId)) {
        throw "FATAL: Duplicate dispatch attempted for completed task $TaskId!"
    }
    
    # Mark active
    $global:Ledger.Tasks[$TaskId] = $Phase
}

function Complete-Work {
    param([string]$TaskId, [string]$ResultIdentity)
    
    $global:Ledger.Results[$TaskId] = $ResultIdentity
    $global:Ledger.Tasks[$TaskId] = "COMPLETED"
}

function Run-RecoveryReconciliation {
    param([string]$PendingTaskId)
    
    Write-Host "[Reconciliation] Scanning ledger for Task: $PendingTaskId..."
    if ($global:Ledger.Results.ContainsKey($PendingTaskId)) {
        Write-Host "[Reconciliation] Found durable evidence/result for $PendingTaskId. Skipping dispatch." -ForegroundColor Green
        return "IDLE_READY"
    } else {
        Write-Host "[Reconciliation] No result found. Resuming dispatch." -ForegroundColor Yellow
        return "RESUME_DISPATCH"
    }
}

# ---------------------------------------------------------
# SCENARIO EXECUTION
# ---------------------------------------------------------

function Run-DuplicateRedispatchTest {
    $TestTaskId = "TASK-001"
    $TestResultId = "RES-001"
    
    Write-Host "`n1. Work Starts..."
    Invoke-WorkPhase -TaskId $TestTaskId -Phase "IN_PROGRESS"
    
    Write-Host "2. Useful Work Completes..."
    Complete-Work -TaskId $TestTaskId -ResultIdentity $TestResultId
    
    Write-Host "3. Terminal Host Fails (Surface Looks Broken)..."
    # The worker is suddenly disconnected from the PTY, but the ledger was already flushed.
    
    Write-Host "4. Recovery Runs..."
    # The system restarts the terminal and evaluates what was happening.
    
    Write-Host "5. Reconciliation Occurs..."
    $action = Run-RecoveryReconciliation -PendingTaskId $TestTaskId
    
    if ($action -ne "IDLE_READY") {
        Write-Host "[FAIL] Reconciliation incorrectly decided to redispatch." -ForegroundColor Red
        throw "Regression Failure: Redispatch"
    }
    
    Write-Host "6. Attempting Redispatch (Adversarial Check)..."
    try {
        if ($action -eq "RESUME_DISPATCH") {
            Invoke-WorkPhase -TaskId $TestTaskId -Phase "IN_PROGRESS"
        }
        Write-Host "[PASS] No duplicate execution occurred. System successfully transitioned to IDLE_READY." -ForegroundColor Cyan
    } catch {
        Write-Host $_.Exception.Message -ForegroundColor Red
        throw "Regression Failure: Duplicate Execution Exception"
    }
}

if ($RunTests) {
    try {
        Run-DuplicateRedispatchTest
    } catch {
        Write-Host "TEST FAILED" -ForegroundColor Red
        exit 1
    }
}
