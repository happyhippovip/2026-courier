# Removes this user's Courier app. An older Program Files copy is removed too
# when this process is allowed to delete it.
param(
    [switch]$RemoveUserData
)

if (-not $env:LOCALAPPDATA) {
    Write-Host "ERROR: LOCALAPPDATA is not set. The uninstaller cannot find the user folder." -ForegroundColor Red
    exit 1
}

$taskName = "CourierWindowsWorker"
$InstallDir = Join-Path $env:LOCALAPPDATA "Courier\app"
$LegacyDir = if ($env:ProgramFiles) { Join-Path $env:ProgramFiles "CourierWorker" } else { "" }

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

if ($LegacyDir -and (Test-Path -LiteralPath $LegacyDir)) {
    try {
        Remove-Item -LiteralPath $LegacyDir -Recurse -Force -ErrorAction Stop
        Write-Host "Removed the older Program Files installation: $LegacyDir"
    } catch {
        Write-Host "ERROR: the older Program Files installation is still present: $LegacyDir" -ForegroundColor Red
        exit 1
    }
}

if ($RemoveUserData) {
    Write-Host "Uninstall complete. User data under AppData\Local\Courier was removed."
} else {
    Write-Host "Uninstall complete. Database and logs in AppData\Local\Courier were preserved."
}
