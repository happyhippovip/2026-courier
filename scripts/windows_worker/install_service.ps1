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

Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal
Write-Host "Courier Windows Worker scheduled task registered to start on boot as SYSTEM."
