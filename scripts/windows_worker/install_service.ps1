# Requires Run as Administrator
$action = "Create"
$taskName = "CourierWindowsWorker"
$scriptPath = "$PSScriptRoot\start.bat"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered existing task."
}

$trigger = New-ScheduledTaskTrigger -AtLogon
$action = New-ScheduledTaskAction -Execute $scriptPath

# Override default Windows task settings which kill the task after 72 hours or on battery
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Days 0) -DisallowStartIfOnBatteries:$false -StopIfGoingOnBatteries:$false -AllowStartIfOnBatteries

# Get current user instead of SYSTEM
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings
Write-Host "Courier Windows Worker scheduled task registered to start on boot as $currentUser."
