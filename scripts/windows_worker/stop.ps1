# Stop only a Courier process this install recorded.
# A missing record is not a reason to stop every Courier.exe on the machine.
param(
    [switch]$AllProfiles,
    [switch]$Library
)

$ErrorActionPreference = "Continue"
$script:failed = $false
$script:stopped = $false

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

function Stop-RecordedPid {
    param([string]$PidFile)
    if (-not (Test-Path -LiteralPath $PidFile)) { return }

    $lines = @(Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue)
    $processId = 0
    $raw = ""
    if ($lines.Count -ge 1) { $raw = [string]$lines[0] }
    if (-not [int]::TryParse($raw.Trim(), [ref]$processId) -or $processId -le 0) {
        Write-Output "ERROR: $PidFile does not contain a process id."
        $script:failed = $true
        return
    }

    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $proc) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        Write-Output "Recorded process $processId is already gone."
        $script:stopped = $true
        return
    }

    if (-not (Test-CourierProcessName -Actual $proc.ProcessName -Expected "Courier")) {
        Write-Output "ERROR: PID $processId is $($proc.ProcessName), not the recorded Courier process. Refusing to stop it."
        $script:failed = $true
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
            Write-Output "ERROR: $PidFile has an unreadable start time. Refusing to stop PID $processId."
            $script:failed = $true
            return
        }
        try {
            $actual = $proc.StartTime.ToUniversalTime()
            $delta = [math]::Abs(($actual - $expected.ToUniversalTime()).TotalSeconds)
        } catch {
            Write-Output "ERROR: could not read the start time of PID $processId. Refusing to stop it."
            $script:failed = $true
            return
        }
        if ($delta -gt 2) {
            Write-Output "ERROR: PID $processId started at a different time. Refusing to stop it."
            $script:failed = $true
            return
        }
    }

    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    $alive = $true
    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Milliseconds 200
        $still = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if (-not $still) { $alive = $false; break }
        try {
            $still.Refresh()
            if ($still.HasExited) { $alive = $false; break }
        } catch {
            $alive = $false
            break
        }
        if ((Test-Path -LiteralPath "/proc") -and -not (Test-Path -LiteralPath "/proc/$processId")) {
            $alive = $false
            break
        }
    }
    if ($alive) {
        Write-Output "ERROR: owned process $processId is still running."
        $script:failed = $true
        return
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Output "Stopped owned process $processId."
    $script:stopped = $true
}

if ($Library) { return }

if (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue) {
    $task = Get-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
    if ($task -and $task.State -eq "Running") {
        Stop-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
        $task = Get-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
        if ($task -and $task.State -eq "Running") {
            Write-Output "ERROR: scheduled task CourierWindowsWorker is still running."
            $script:failed = $true
        } else {
            Write-Output "Stopped scheduled task CourierWindowsWorker."
            $script:stopped = $true
        }
    }
}

$pidFiles = New-Object System.Collections.Generic.List[string]
$pidFiles.Add((Join-Path $PSScriptRoot "worker.pid"))
$homes = New-Object System.Collections.Generic.List[string]
if ($env:COURIER_HOME) { $homes.Add($env:COURIER_HOME) }
if ($env:LOCALAPPDATA) { $homes.Add((Join-Path $env:LOCALAPPDATA "Courier")) }
if ($AllProfiles -and $env:SystemDrive) {
    $users = Join-Path $env:SystemDrive "Users"
    if (Test-Path -LiteralPath $users) {
        Get-ChildItem -LiteralPath $users -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $homes.Add((Join-Path $_.FullName "AppData\Local\Courier"))
        }
    }
}
foreach ($dataHome in $homes) {
    $pidFiles.Add((Join-Path $dataHome "run\launcher.pid"))
}

$seen = @{}
foreach ($file in $pidFiles) {
    if ($seen.ContainsKey($file)) { continue }
    $seen[$file] = $true
    Stop-RecordedPid $file
}

if ($script:failed) {
    Write-Output "Courier stop failed: an owned process is still running."
    exit 1
}
if (-not $script:stopped) {
    Write-Output "No owned Courier process was recorded."
    exit 2
}
Write-Output "Stopped the owned Courier process."
exit 0
