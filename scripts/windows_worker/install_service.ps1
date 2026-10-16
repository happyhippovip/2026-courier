param(
    [switch]$PerUser = $false
)

$taskName = "CourierWindowsWorker"
$scriptPath = "$PSScriptRoot\Courier.exe"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered existing task."
}

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($IsAdmin -and -not $PerUser) {
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $action = New-ScheduledTaskAction -Execute $scriptPath
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal
    Write-Host "Courier Windows Worker scheduled task registered under SYSTEM (AtStartup)."
} else {
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $action = New-ScheduledTaskAction -Execute $scriptPath
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal
    Write-Host "Courier Windows Worker scheduled task registered for current user ($env:USERNAME) (AtLogOn)."
}
