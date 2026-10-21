# Removes Courier for the current user. No administrator needed.
#
# Order: stop this user's running Courier (by its recorded PID only), remove
# the logon task, delete the program files, then remove configuration and
# runtime state. The database (courier.db) and the logs stay, so a reinstall
# keeps the history.
param (
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\Courier"),
    [string]$CourierHome = $(if ($env:COURIER_HOME) { $env:COURIER_HOME } else { Join-Path $env:LOCALAPPDATA "Courier" }),
    [string]$TaskName = "CourierWindowsWorker"
)

$ErrorActionPreference = "Stop"

$stopScript = Join-Path $PSScriptRoot "stop.ps1"
if (-not (Test-Path $stopScript)) { $stopScript = Join-Path $InstallDir "stop.ps1" }
if (Test-Path $stopScript) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stopScript -CourierHome $CourierHome
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Courier is still running. Nothing was removed." -ForegroundColor Red
        exit 1
    }
}

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Write-Host "ERROR: Scheduled task $TaskName could not be removed." -ForegroundColor Red
        exit 1
    }
    Write-Host "Removed the logon task $TaskName."
}

# PowerShell has already read this script, so it may delete its own folder;
# only the working directory must not be inside it.
Set-Location $env:TEMP
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force -ErrorAction Stop $InstallDir
    if (Test-Path $InstallDir) {
        Write-Host "ERROR: Installation folder $InstallDir could not be removed." -ForegroundColor Red
        exit 1
    }
    Write-Host "Removed $InstallDir."
}

$configFile = Join-Path $CourierHome "config.json"
$runDir = Join-Path $CourierHome "run"
if (Test-Path $configFile) { Remove-Item -Force $configFile }
if (Test-Path $runDir) { Remove-Item -Recurse -Force $runDir }

$legacy = Join-Path $env:ProgramFiles "CourierWorker"
if (Test-Path $legacy) {
    Write-Host "An older machine-wide install remains in $legacy. Remove it as administrator." -ForegroundColor Yellow
}

Write-Host "Uninstall complete. Database and logs in $CourierHome were kept."
exit 0
