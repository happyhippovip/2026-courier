# Install Courier for the current user.
# Program files default to Program Files\CourierWorker (-InstallRoot overrides).
# The data directory defaults to %LOCALAPPDATA%\Courier (-DataRoot overrides).
# The logon task is CourierWindowsWorker, the name uninstall.ps1 removes.
# -NoTask copies files and leaves task registration to the caller.
# Exit 0: success.
# Exit 1: a directory was rejected or could not be prepared.
# Exit 2: copying program files failed.
# Exit 3: the logon task could not be registered.
# Running the script again refreshes program files and replaces that same task.
# Files already in the data directory are left in place. This script does not
# ask questions and does not write a controller credential.

param(
    [string]$InstallRoot = "",
    [string]$DataRoot = "",
    [switch]$NoTask
)

$ErrorActionPreference = "Stop"
$TaskName = "CourierWindowsWorker"

function Test-IsNestedUnder {
    param(
        [string]$Child,
        [string]$Parent
    )
    $parentFull = [System.IO.Path]::GetFullPath($Parent)
    $childFull = [System.IO.Path]::GetFullPath($Child)
    if (-not $parentFull.EndsWith('\')) {
        $parentFull = $parentFull + '\'
    }
    if (-not $childFull.EndsWith('\')) {
        $childFull = $childFull + '\'
    }
    return $childFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)
}

try {
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
        $InstallRoot = Join-Path $env:ProgramFiles "CourierWorker"
    }
    if ([string]::IsNullOrWhiteSpace($DataRoot)) {
        $DataRoot = Join-Path $env:LOCALAPPDATA "Courier"
    }
    if (Test-IsNestedUnder -Child $InstallRoot -Parent $PSScriptRoot) {
        Write-Host "InstallRoot must be outside the installer source directory."
        exit 1
    }
    if (Test-IsNestedUnder -Child $DataRoot -Parent $PSScriptRoot) {
        Write-Host "DataRoot must be outside the installer source directory."
        exit 1
    }
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
} catch {
    Write-Host "Cannot prepare Courier directories: $($_.Exception.Message)"
    exit 1
}

try {
    # Copy each child on its own. A wildcard plus -Recurse is unreliable on
    # Windows PowerShell 5.1 and can skip or reject directories.
    Get-ChildItem -LiteralPath $PSScriptRoot -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $InstallRoot -Recurse -Force
    }
} catch {
    Write-Host "Failed to copy Courier files: $($_.Exception.Message)"
    exit 2
}

if ($NoTask) {
    Write-Host "Courier files installed to $InstallRoot. Scheduled task was not registered."
    exit 0
}

try {
    $principalUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ([string]::IsNullOrWhiteSpace($principalUser)) {
        Write-Host "Cannot determine the installing user for task $TaskName."
        exit 3
    }
    $existing = $null
    try {
        $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    } catch {
        $existing = $null
    }
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    $exePath = Join-Path $InstallRoot "Courier.exe"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $principalUser
    $action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $InstallRoot
    $principal = New-ScheduledTaskPrincipal -UserId $principalUser -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $TaskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings -Description "Starts Courier at logon for the installing user." | Out-Null
} catch {
    Write-Host "Failed to register scheduled task ${TaskName}: $($_.Exception.Message)"
    exit 3
}

Write-Host "Courier installed to $InstallRoot. Task $TaskName runs at logon as $principalUser."
exit 0
