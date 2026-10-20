# Requires Run as Administrator
param(
    [switch]$RemoveUserData
)

if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Please run as Administrator." -ForegroundColor Red
    exit 1
}

$taskName = "CourierWindowsWorker"
$InstallDir = "$env:ProgramFiles\CourierWorker"

& "$PSScriptRoot\stop.ps1" -AllProfiles
if ($LASTEXITCODE -eq 1) {
    Write-Host "ERROR: an owned Courier process is still running. Files were not removed." -ForegroundColor Red
    exit 1
}

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered and stopped Courier Windows Worker scheduled task."
} else {
    Write-Host "Task $taskName does not exist."
}

$usersDir = if ($env:SystemDrive) { Join-Path $env:SystemDrive "Users" } else { "C:\Users" }
& "$PSScriptRoot\uninstall_user_data.ps1" -UsersRoot $usersDir -IncludeEnvironment -RemoveUserData:$RemoveUserData
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: user data cleanup failed. Program files were left in place." -ForegroundColor Red
    exit $LASTEXITCODE
}

if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
    Write-Host "Removed installation directory: $InstallDir"
}

if ($RemoveUserData) {
    Write-Host "Uninstall complete. User data under AppData\Local\Courier was removed."
} else {
    Write-Host "Uninstall complete. Database and logs in AppData\Local\Courier were preserved."
}
