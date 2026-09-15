param(
    [Parameter(Mandatory=$true)]
    [string]$TaskId
)

if ($TaskId -notmatch '^[a-zA-Z0-9_-]+$') {
    Write-Error "Invalid TaskId"
    exit 1
}

$RuntimeDir = "C:\Dev\Windows-AI-OS\runtime"
$Inbox = "$RuntimeDir\tasks\inbox"
$Processing = "$RuntimeDir\tasks\processing"
$Completed = "$RuntimeDir\tasks\completed"
$Failed = "$RuntimeDir\tasks\failed"
$Results = "$RuntimeDir\results"

$InboxTask = "$Inbox\$TaskId.json"
$ProcTask = "$Processing\$TaskId.json"

if (-not (Test-Path $InboxTask)) {
    exit 0
}

try {
    Move-Item -Path $InboxTask -Destination $ProcTask -ErrorAction Stop
} catch {
    exit 0
}

$TaskContent = Get-Content -Path $ProcTask -Raw | ConvertFrom-Json
$Action = $TaskContent.ACTION

if ($Action -eq 'HEALTH_CHECK') {
    $Output = "WINDOWS_WORKER_HEALTHY"
    $Status = "COMPLETED"
    $ExitCode = 0
} elseif ($Action -eq 'RUN_TESTS') {
    $Script = "C:\Dev\Windows-AI-OS\scripts\Test-WindowsAIHost.ps1"
    if (Test-Path $Script) {
        $Output = & $Script | Out-String
        $Status = "COMPLETED"
        $ExitCode = $LASTEXITCODE
    } else {
        $Output = "SCRIPT_NOT_FOUND"
        $Status = "FAILED"
        $ExitCode = 1
    }
} elseif ($Action -eq 'BUILD_PROJECT') {
    $Output = "Project build simulated."
    $Status = "COMPLETED"
    $ExitCode = 0
} else {
    $Output = "UNSUPPORTED_ACTION: $Action"
    $Status = "FAILED"
    $ExitCode = 1
}

$ResultJson = @{
    TASK_ID = $TaskId
    ACTION = $Action
    STATUS = $Status
    EXIT_CODE = $ExitCode
    OUTPUT = $Output
} | ConvertTo-Json

$TmpResult = "$Results\$TaskId.json.tmp"
$FinalResult = "$Results\$TaskId.json"
Set-Content -Path $TmpResult -Value $ResultJson
Move-Item -Path $TmpResult -Destination $FinalResult -Force

if ($Status -eq "COMPLETED") {
    Move-Item -Path $ProcTask -Destination "$Completed\$TaskId.json" -Force
} else {
    Move-Item -Path $ProcTask -Destination "$Failed\$TaskId.json" -Force
}
