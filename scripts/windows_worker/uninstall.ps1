# Requires Run as Administrator
if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: Please run as Administrator." -ForegroundColor Red
    exit 1
}

$taskName = "CourierWindowsWorker"
$InstallDir = "$env:ProgramFiles\CourierWorker"

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered and stopped Courier Windows Worker scheduled task."
} else {
    Write-Host "Task $taskName does not exist."
}

if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
    Write-Host "Removed installation directory: $InstallDir"
}

Write-Host "Removing credentials (config.json and run/) from user profiles..."
$usersDir = "C:\Users"
Get-ChildItem -Path $usersDir | Where-Object { $_.PSIsContainer } | ForEach-Object {
    $userCourierDir = Join-Path $_.FullName "AppData\Local\Courier"
    if (Test-Path $userCourierDir) {
        $configFile = Join-Path $userCourierDir "config.json"
        $runDir = Join-Path $userCourierDir "run"
        if (Test-Path $configFile) { Remove-Item -Force $configFile }
        if (Test-Path $runDir) { Remove-Item -Recurse -Force $runDir }
    }
}

Write-Host "Uninstall complete. Database and logs in %LOCALAPPDATA%\Courier were preserved."
