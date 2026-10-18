# Installs Courier for the current user. No questions, no administrator.
#
# Courier runs locally: the launcher starts the controller, the worker and the
# hub, and the controller writes its own token. The installer therefore asks
# for no server URL and no API key and never writes run\controller.token.
param (
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "Programs\Courier"),
    [string]$CourierHome = $(if ($env:COURIER_HOME) { $env:COURIER_HOME } else { Join-Path $env:LOCALAPPDATA "Courier" }),
    [string]$TaskName = "CourierWindowsWorker",
    # Do not start Courier when the user logs on.
    [switch]$NoAutoStart,
    # Do not start Courier now.
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

Write-Host "========================================"
Write-Host " Courier Installer"
Write-Host "========================================"

New-Item -ItemType Directory -Force -Path $CourierHome | Out-Null
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Keep an existing configuration (ports, worker id); only add a worker id.
$configPath = Join-Path $CourierHome "config.json"
$config = [ordered]@{}
if (Test-Path $configPath) {
    Write-Host "Keeping existing configuration $configPath."
    $existing = Get-Content $configPath -Raw | ConvertFrom-Json
    foreach ($property in $existing.PSObject.Properties) { $config[$property.Name] = $property.Value }
}
if (-not $config["COURIER_WORKER_ID"]) {
    $config["COURIER_WORKER_ID"] = "WIN-" + [guid]::NewGuid().ToString().Substring(0, 8)
}
$config | ConvertTo-Json | Set-Content -Path $configPath -Encoding UTF8

Write-Host "Copying files to $InstallDir..."
Copy-Item -Path (Join-Path $PSScriptRoot "*") -Destination $InstallDir -Recurse -Force
$launcher = Join-Path $InstallDir "Courier.exe"

# A checked-in Courier.exe can be older than its source. When the source is
# here, build the installed launcher from it with the csc that ships with the
# .NET Framework on Windows 10 and 11. A packaged install has no source and
# keeps the Courier.exe that build_package.ps1 built.
$source = Join-Path $PSScriptRoot "launcher\CourierLauncher.cs"
$csc = Join-Path $env:windir "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if ((Test-Path $source) -and (Test-Path $csc)) {
    & $csc /nologo /target:winexe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/out:$launcher" $source
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Could not build Courier.exe from $source." -ForegroundColor Red
        exit 1
    }
    Write-Host "Built Courier.exe from $source."
}
if (-not (Test-Path $launcher)) {
    Write-Host "ERROR: $launcher is missing after copy." -ForegroundColor Red
    exit 1
}

if (-not $NoAutoStart) {
    # A logon task of this user with normal rights: the same LOCALAPPDATA as
    # the user, no SYSTEM account, no elevation.
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $action = New-ScheduledTaskAction -Execute $launcher -WorkingDirectory $InstallDir
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    try {
        Register-ScheduledTask -TaskName $TaskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings -Force | Out-Null
        Write-Host "Courier starts when $user logs on (task $TaskName)."
    } catch {
        Write-Host "WARNING: Could not register the logon task: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Start Courier with $launcher." -ForegroundColor Yellow
    }
}

if (-not $NoLaunch) {
    Start-Process -FilePath $launcher -WorkingDirectory $InstallDir
    Write-Host "Courier started."
}

Write-Host "Courier installed in $InstallDir. Data: $CourierHome"
exit 0
