# Requires Run as Administrator
$action = "Create"
$taskName = "CourierWindowsWorker"
$scriptPath = "$PSScriptRoot\start.bat"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered existing task."
}

$trigger = New-ScheduledTaskTrigger -AtStartup
$action = New-ScheduledTaskAction -Execute $scriptPath

# Run as SYSTEM for unattended reboot-safe operation
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Ensure no duplicate instances on restart, auto-restart on unexpected failure, unlimited execution time
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings
Write-Host "Courier Windows Worker scheduled task registered to start on boot as SYSTEM with duplicate prevention."
