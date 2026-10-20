# Registers the worker for the user who installed it.
# The key is in that user's %LOCALAPPDATA%\Courier. A SYSTEM task has a
# different LOCALAPPDATA and would start with no key.
$taskName = "CourierWindowsWorker"
$scriptPath = "$PSScriptRoot\Courier.exe"
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Write-Host "ERROR: the scheduled task is still present: $taskName" -ForegroundColor Red
        exit 1
    }
    Write-Host "Unregistered existing task."
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$action = New-ScheduledTaskAction -Execute $scriptPath
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
# Task Scheduler defaults stop a task after 72 hours and never restart it after
# a failure. The worker runs unattended, so: no time limit, restart after a
# failure, and never a second copy.
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings -ErrorAction Stop
} catch {
    Write-Host "ERROR: the scheduled task was not registered: $taskName" -ForegroundColor Red
    exit 1
}
if (-not (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: the scheduled task was not registered: $taskName" -ForegroundColor Red
    exit 1
}
Write-Host "Courier Windows Worker scheduled task registered for $userId at logon."
