# Register CourierWindowsWorker for the current user at logon.
# Same task name install.ps1 and uninstall.ps1 use. Re-running replaces it.
# No elevation. The worker then sees this user's %LOCALAPPDATA%\Courier.

param(
    [string]$TaskName = "CourierWindowsWorker",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

function Test-SameAccount {
    param([string]$Left, [string]$Right)
    if ([string]::IsNullOrWhiteSpace($Left) -or [string]::IsNullOrWhiteSpace($Right)) {
        return $false
    }
    if ($Left.Equals($Right, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    # Scheduled tasks store the account name; WindowsIdentity includes the machine.
    $leftTail = ($Left -split '\\')[-1]
    $rightTail = ($Right -split '\\')[-1]
    if ([string]::IsNullOrWhiteSpace($leftTail) -or [string]::IsNullOrWhiteSpace($rightTail)) {
        return $false
    }
    return $leftTail.Equals($rightTail, [System.StringComparison]::OrdinalIgnoreCase)
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = $PSScriptRoot
}

$principalUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if ([string]::IsNullOrWhiteSpace($principalUser)) {
    Write-Host "Cannot determine the current user for task $TaskName."
    exit 1
}

$existing = $null
try {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
} catch {
    $existing = $null
}
$previousXml = $null
if ($null -ne $existing) {
    $previousXml = Export-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($previousXml)) {
        Write-Host "Cannot read the existing scheduled task $TaskName. Leaving it in place."
        exit 1
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
}

$exePath = Join-Path $InstallDir "Courier.exe"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $principalUser
$action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $InstallDir
$principal = New-ScheduledTaskPrincipal -UserId $principalUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask -TaskName $TaskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
} catch {
    if ($null -ne $previousXml) {
        try {
            Register-ScheduledTask -Xml $previousXml -TaskName $TaskName -ErrorAction Stop | Out-Null
        } catch {
            Write-Host "Failed to restore scheduled task ${TaskName}: $($_.Exception.Message)"
            exit 1
        }
    }
    Write-Host "Failed to register scheduled task ${TaskName}: $($_.Exception.Message)"
    exit 1
}

$checked = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
if (-not (Test-SameAccount $checked.Principal.UserId $principalUser)) {
    Write-Host "Scheduled task $TaskName principal is '$($checked.Principal.UserId)', expected '$principalUser'."
    exit 1
}

Write-Host "Courier Windows Worker scheduled task registered for $principalUser."
exit 0
