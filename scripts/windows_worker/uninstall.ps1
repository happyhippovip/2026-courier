$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$taskName = "CourierWindowsWorker"
$InstallDir = if ($IsAdmin) { "$env:ProgramFiles\CourierWorker" } else { "$env:LOCALAPPDATA\CourierWorker" }

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Unregistered and stopped Courier Windows Worker scheduled task."
} else {
    Write-Host "Task $taskName does not exist."
}

if (Test-Path -LiteralPath $InstallDir) {
    try {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Error "Courier uninstall not proven: install directory was not removed."
        exit 1
    }
    if (Test-Path -LiteralPath $InstallDir) {
        Write-Error "Courier uninstall not proven: install directory remains."
        exit 1
    }
    Write-Host "Removed installation directory: $InstallDir"
}

if ($IsAdmin) {
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
} else {
    Write-Host "Removing credentials (config.json and run/) from current user profile..."
    $userCourierDir = "$env:LOCALAPPDATA\Courier"
    if (Test-Path $userCourierDir) {
        $configFile = Join-Path $userCourierDir "config.json"
        $runDir = Join-Path $userCourierDir "run"
        if (Test-Path $configFile) { Remove-Item -Force $configFile }
        if (Test-Path $runDir) { Remove-Item -Recurse -Force $runDir }
    }
}

Write-Host "Uninstall complete. Database and logs in %LOCALAPPDATA%\Courier were preserved."
