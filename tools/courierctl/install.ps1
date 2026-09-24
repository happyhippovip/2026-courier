# Windows installer for courierctl
[CmdletBinding()]
param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $InstallDir) {
    if ($env:LOCALAPPDATA) {
        $InstallDir = Join-Path $env:LOCALAPPDATA "Courier\bin"
    } else {
        $InstallDir = Join-Path $HOME ".local\bin"
    }
}

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Copy-Item (Join-Path $ScriptDir "courierctl.py") -Destination (Join-Path $InstallDir "courierctl.py") -Force
Copy-Item (Join-Path $ScriptDir "courierctl.cmd") -Destination (Join-Path $InstallDir "courierctl.cmd") -Force

# Check and update PATH in User environment if not present
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$Paths = if ($UserPath) { ($UserPath -split ";") | Where-Object { $_ -ne "" } } else { @() }
if ($Paths -notcontains $InstallDir) {
    $NewUserPath = if ($UserPath) { "$UserPath;$InstallDir" } else { $InstallDir }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
    $env:Path = "$env:Path;$InstallDir"
    Write-Host "Added $InstallDir to User PATH."
}

Write-Host "Installed courierctl to $InstallDir\courierctl.cmd"
Write-Host ""
Write-Host "Please set your environment variables to use it:"
Write-Host '$env:COURIER_SERVER = "http://localhost:8080"'
Write-Host '$env:COURIER_API_KEY = "your_secure_api_key_here"'
