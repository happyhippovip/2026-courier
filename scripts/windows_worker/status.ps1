# Report only a Courier process this install recorded.
# Another Courier.exe on the machine is not this install.
param(
    [switch]$Library
)

$ErrorActionPreference = "Continue"
$script:running = $false
$script:sawRecord = $false

function Test-CourierProcessName {
    param(
        [string]$Actual,
        [string]$Expected
    )
    if ([string]::IsNullOrWhiteSpace($Actual) -or [string]::IsNullOrWhiteSpace($Expected)) {
        return $false
    }
    # Windows names a second Courier.exe "Courier#1". That is still Courier.
    $left = [IO.Path]::GetFileNameWithoutExtension($Actual.Split('#')[0].Trim())
    $right = [IO.Path]::GetFileNameWithoutExtension($Expected.Split('#')[0].Trim())
    return [bool]($left -and $right -and ($left -eq $right))
}

function Test-RecordedPid {
    param([string]$PidFile)
    if (-not (Test-Path -LiteralPath $PidFile)) { return }
    $script:sawRecord = $true

    $lines = @(Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue)
    $processId = 0
    $raw = ""
    if ($lines.Count -ge 1) { $raw = [string]$lines[0] }
    if (-not [int]::TryParse($raw.Trim(), [ref]$processId) -or $processId -le 0) {
        Write-Output "ERROR: $PidFile does not contain a process id."
        return
    }

    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $proc -or $proc.HasExited) {
        Write-Output "Recorded process $processId is not running."
        return
    }
    if (-not (Test-CourierProcessName -Actual $proc.ProcessName -Expected "Courier")) {
        Write-Output "Recorded PID $processId is $($proc.ProcessName), not Courier."
        return
    }

    if ($lines.Count -ge 2 -and -not [string]::IsNullOrWhiteSpace([string]$lines[1])) {
        $expected = [datetime]::MinValue
        $parsed = [datetime]::TryParse(
            [string]$lines[1],
            [cultureinfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind,
            [ref]$expected)
        if (-not $parsed) {
            Write-Output "ERROR: $PidFile has an unreadable start time."
            return
        }
        try {
            $actual = $proc.StartTime.ToUniversalTime()
            $delta = [math]::Abs(($actual - $expected.ToUniversalTime()).TotalSeconds)
        } catch {
            Write-Output "ERROR: could not read the start time of PID $processId."
            return
        }
        if ($delta -gt 2) {
            Write-Output "Recorded PID $processId does not match the saved start time."
            return
        }
    }

    Write-Output "Courier is running (PID $processId)."
    $script:running = $true
}

if ($Library) { return }

if (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue) {
    $task = Get-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
    if ($task) {
        $script:sawRecord = $true
        if ($task.State -eq "Running") {
            Write-Output "Scheduled task CourierWindowsWorker is running."
            $script:running = $true
        } else {
            Write-Output "Scheduled task CourierWindowsWorker is $($task.State)."
        }
    }
}

$pidFiles = New-Object System.Collections.Generic.List[string]
$pidFiles.Add((Join-Path $PSScriptRoot "worker.pid"))
$homes = New-Object System.Collections.Generic.List[string]
if ($env:COURIER_HOME) { $homes.Add($env:COURIER_HOME) }
if ($env:LOCALAPPDATA) { $homes.Add((Join-Path $env:LOCALAPPDATA "Courier")) }
foreach ($dataHome in $homes) {
    $pidFiles.Add((Join-Path $dataHome "run\launcher.pid"))
}

$seen = @{}
foreach ($file in $pidFiles) {
    if ($seen.ContainsKey($file)) { continue }
    $seen[$file] = $true
    Test-RecordedPid $file
}

if ($script:running) { exit 0 }
if (-not $script:sawRecord) {
    Write-Output "No owned Courier process was recorded."
}
exit 2
