# Remove Courier's scheduled task, install directory, and a process only when
# its executable path is this install's Courier.exe.
# install.ps1 and install_service.ps1 both register CourierWindowsWorker.
# That one name covers the legacy SYSTEM startup task and the current-user
# logon task. Re-query after removal. Exit 0 when nothing is installed.
# Exit 1 when a targeted task, path, or attributable process remains.
# No elevation. Does not change permissions or machine policy.

param(
    [string[]]$TaskName = @("CourierWindowsWorker"),
    [string]$InstallDir = "",
    [string]$DataDir = "",
    [switch]$SimulateRemovalFailure
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = Join-Path $env:ProgramFiles "CourierWorker"
}
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    $DataDir = Join-Path $env:LOCALAPPDATA "Courier"
}

$problems = @()
$sawWork = $false
$exePath = Join-Path $InstallDir "Courier.exe"

foreach ($name in $TaskName) {
    if ([string]::IsNullOrWhiteSpace($name)) {
        continue
    }
    try {
        $found = @(Get-ScheduledTask -TaskName $name -ErrorAction Stop)
    } catch {
        $category = [string]$_.CategoryInfo.Category
        $errorId = [string]$_.FullyQualifiedErrorId
        if ($category -eq 'ObjectNotFound' -or $errorId -like '*NotFound*') {
            $found = @()
        } else {
            $problems += "Could not query scheduled task ${name}: $($_.Exception.Message)"
            $found = @()
        }
    }
    if ($found.Count -eq 0) {
        continue
    }
    $sawWork = $true
    if (-not $SimulateRemovalFailure) {
        foreach ($task in $found) {
            try {
                Stop-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -ErrorAction SilentlyContinue | Out-Null
            } catch {
            }
            try {
                Unregister-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Confirm:$false -ErrorAction Stop
            } catch {
            }
        }
    }
    try {
        $remaining = @(Get-ScheduledTask -TaskName $name -ErrorAction Stop)
    } catch {
        $category = [string]$_.CategoryInfo.Category
        $errorId = [string]$_.FullyQualifiedErrorId
        if ($category -eq 'ObjectNotFound' -or $errorId -like '*NotFound*') {
            $remaining = @()
        } else {
            $problems += "Could not query scheduled task ${name}: $($_.Exception.Message)"
            $remaining = @()
        }
    }
    if ($remaining.Count -gt 0) {
        $problems += "Scheduled task $name is still registered."
    }
}

$running = @()
try {
    $running = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.ExecutablePath -and ($_.ExecutablePath -ieq $exePath)
    })
} catch {
    $problems += "Could not query processes to verify Courier.exe at $exePath is stopped."
}
if ($running.Count -gt 0) {
    $sawWork = $true
    if (-not $SimulateRemovalFailure) {
        foreach ($proc in $running) {
            try {
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            } catch {
            }
        }
        try {
            $running = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
                $_.ExecutablePath -and ($_.ExecutablePath -ieq $exePath)
            })
        } catch {
            $problems += "Could not query processes to verify Courier.exe at $exePath is stopped."
            $running = @()
        }
    }
    if ($running.Count -gt 0) {
        $ids = ($running | ForEach-Object { $_.ProcessId }) -join ","
        $problems += "Courier process still running at ${exePath} (pid $ids)."
    }
}

foreach ($path in @(
        $InstallDir,
        (Join-Path $DataDir "config.json"),
        (Join-Path $DataDir "run")
    )) {
    if (-not (Test-Path -LiteralPath $path)) {
        continue
    }
    $sawWork = $true
    if (-not $SimulateRemovalFailure) {
        try {
            Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
        } catch {
        }
    }
    if (Test-Path -LiteralPath $path) {
        $problems += "Path still present: $path"
    }
}

if ($problems.Count -gt 0) {
    foreach ($problem in $problems) {
        Write-Host $problem
    }
    exit 1
}
if (-not $sawWork) {
    Write-Host "nothing installed"
    exit 0
}
Write-Host "Uninstall verified."
exit 0
