$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

$taskName = "CourierWindowsWorker"
$InstallDir = if ($env:COURIER_INSTALL_DIR) {
    $env:COURIER_INSTALL_DIR
} elseif (Test-Path -LiteralPath "$env:ProgramFiles\CourierWorker") {
    "$env:ProgramFiles\CourierWorker"
} else {
    "$env:LOCALAPPDATA\CourierWorker"
}

if ($IsAdmin) {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Unregistered and stopped Courier Windows Worker scheduled task."
    } else {
        Write-Host "Task $taskName does not exist."
    }
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

Write-Host "Uninstall complete. User data in %LOCALAPPDATA%\Courier was preserved."
