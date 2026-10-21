param (
    [string]$ServerArg = "",
    [string]$ApiKeyArg = "",
    [string]$WorkerIdArg = ""
)

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-Not $IsAdmin) {
    Write-Host "WARNING: Not running as Administrator. Scheduled Task will not be registered." -ForegroundColor Yellow
}

$InstallDir = "$env:ProgramFiles\CourierWorker"
$DataDir = "$env:LOCALAPPDATA\Courier"
$ConfigPath = Join-Path $DataDir "config.json"

Write-Host "========================================"
Write-Host " Courier Windows Worker Installer"
Write-Host "========================================"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "run") | Out-Null
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$Server = $ServerArg
$ApiKey = $ApiKeyArg
$WorkerId = $WorkerIdArg

$progDataDir = [System.Environment]::ExpandEnvironmentVariables("%PROGRAMDATA%\CourierWorker")
$progDataConfig = Join-Path $progDataDir "config.json"

if (Test-Path $ConfigPath) {
    Write-Host "Found existing configuration in LocalAppData."
    $existing = Get-Content $ConfigPath | ConvertFrom-Json
    if (-not $Server) { $Server = $existing.COURIER_SERVER }
    if (-not $ApiKey) {
        if ($existing.COURIER_API_KEY) { $ApiKey = $existing.COURIER_API_KEY }
        else {
            $tokenPath = Join-Path $DataDir "run\controller.token"
            if (Test-Path $tokenPath) { $ApiKey = Get-Content $tokenPath }
        }
    }
    if (-not $WorkerId) { $WorkerId = $existing.COURIER_WORKER_ID }
} elseif (Test-Path $progDataConfig) {
    Write-Host "Found existing configuration in ProgramData."
    $existing = Get-Content $progDataConfig | ConvertFrom-Json
    if (-not $Server) { $Server = $existing.COURIER_SERVER }
    if (-not $ApiKey) { $ApiKey = $existing.COURIER_API_KEY }
    if (-not $WorkerId) { $WorkerId = $existing.COURIER_WORKER_ID }
}

if (-not $Server) {
    $Server = Read-Host "Enter Courier Server URL (default: http://192.168.178.162:8080)"
    if (-not $Server) { $Server = "http://192.168.178.162:8080" }
}
if (-not $ApiKey) {
    $ApiKey = Read-Host "Enter Courier API Key"
}
if (-not $WorkerId) {
    $WorkerId = Read-Host "Enter a unique Worker ID (default: auto-generated)"
    if (-not $WorkerId) { $WorkerId = "WIN-$( [guid]::NewGuid().ToString().Substring(0,8) )" }
}

$configObj = @{
    COURIER_SERVER = $Server
    COURIER_WORKER_ID = $WorkerId
    COURIER_API_KEY = $ApiKey
}
$configObj | ConvertTo-Json | Set-Content $ConfigPath

if (-not (Test-Path $progDataDir)) { New-Item -ItemType Directory -Force -Path $progDataDir | Out-Null }
$configObj | ConvertTo-Json | Set-Content $progDataConfig

$tokenPath = Join-Path $DataDir "run\controller.token"
if ($ApiKey) {
    $ApiKey | Set-Content $tokenPath -NoNewline
}

# Also sync to SYSTEM profile if running elevated so the Scheduled Task has immediate access
$systemProfileData = "$env:SystemRoot\system32\config\systemprofile\AppData\Local\Courier"
if ($IsAdmin -and (Test-Path (Split-Path $systemProfileData))) {
    New-Item -ItemType Directory -Force -Path $systemProfileData | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $systemProfileData "run") | Out-Null
    $configObj | ConvertTo-Json | Set-Content (Join-Path $systemProfileData "config.json")
    if ($ApiKey) {
        $ApiKey | Set-Content (Join-Path $systemProfileData "run\controller.token") -NoNewline
    }
}

Write-Host "Configuration saved to $ConfigPath and $progDataConfig."
Write-Host "Token saved to $tokenPath."

Write-Host "Copying files to $InstallDir..."
Get-ChildItem -Path $PSScriptRoot -Exclude "dist*", "*.zip", "__pycache__" | Copy-Item -Destination $InstallDir -Recurse -Force

if ($IsAdmin) {
    Write-Host "Registering Scheduled Task..."
    $taskName = "CourierWindowsWorker"
    $scriptPath = "$InstallDir\Courier.exe"

    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    $trigger = New-ScheduledTaskTrigger -AtStartup
    $action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $InstallDir
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings | Out-Null

    Write-Host "Starting Service..."
    Start-ScheduledTask -TaskName $taskName
} else {
    Write-Host "Skipped Scheduled Task registration (requires Administrator)." -ForegroundColor Yellow
}

Write-Host "Courier installed successfully!"
