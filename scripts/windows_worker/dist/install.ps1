param (
    [string]$ServerArg = "",
    [string]$ApiKeyArg = "",
    [string]$WorkerIdArg = ""
)

if (-not $env:LOCALAPPDATA) {
    Write-Host "ERROR: LOCALAPPDATA is not set. The installer cannot choose a user folder." -ForegroundColor Red
    exit 1
}

# The program and the ledger live in the installing user's profile.
# No Administrator right and no Program Files copy.
$InstallDir = Join-Path $env:LOCALAPPDATA "Courier\app"
$DataDir = Join-Path $env:LOCALAPPDATA "Courier"
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

if (Test-Path $ConfigPath) {
    Write-Host "Found existing configuration."
    $existing = Get-Content $ConfigPath | ConvertFrom-Json
    if (-not $Server) { $Server = $existing.COURIER_SERVER }
    if (-not $ApiKey) {
        $tokenPath = Join-Path $DataDir "run\controller.token"
        if (Test-Path $tokenPath) {
            $ApiKey = Get-Content $tokenPath
        }
    }
    if (-not $WorkerId) { $WorkerId = $existing.COURIER_WORKER_ID }
}

function Test-CanPrompt {
    try {
        return [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
    } catch {
        return $false
    }
}

if (-not $Server) {
    if (-not (Test-CanPrompt)) {
        Write-Host "ERROR: a Courier server URL is required. Pass -ServerArg." -ForegroundColor Red
        exit 1
    }
    $Server = Read-Host "Enter Courier Server URL (for example http://127.0.0.1:8080)"
    if (-not $Server) {
        Write-Host "ERROR: a Courier server URL is required. Pass -ServerArg." -ForegroundColor Red
        exit 1
    }
}
if (-not $ApiKey) {
    if (-not (Test-CanPrompt)) {
        Write-Host "ERROR: a Courier API key is required. Pass -ApiKeyArg." -ForegroundColor Red
        exit 1
    }
    $ApiKey = Read-Host "Enter Courier API Key"
    if (-not $ApiKey) {
        Write-Host "ERROR: a Courier API key is required. Pass -ApiKeyArg." -ForegroundColor Red
        exit 1
    }
}
if ($ApiKey.Length -lt 32) {
    Write-Host "ERROR: the API key must be at least 32 characters. Pass -ApiKeyArg." -ForegroundColor Red
    exit 1
}
if (-not $WorkerId) {
    if (Test-CanPrompt) {
        $WorkerId = Read-Host "Enter a unique Worker ID (default: auto-generated)"
    }
    if (-not $WorkerId) { $WorkerId = "WIN-$( [guid]::NewGuid().ToString().Substring(0,8) )" }
}

$configObj = @{
    COURIER_SERVER = $Server
    COURIER_WORKER_ID = $WorkerId
}
$configObj | ConvertTo-Json | Set-Content $ConfigPath

$tokenPath = Join-Path $DataDir "run\controller.token"
$ApiKey | Set-Content $tokenPath -NoNewline
# The installing user runs the task. Other local users must not read the token.
$ownerSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls $tokenPath /inheritance:r /grant:r "*${ownerSid}:(R)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: could not restrict access to $tokenPath." -ForegroundColor Red
    exit 1
}

Write-Host "Configuration saved to $ConfigPath."
Write-Host "Token saved to $tokenPath."

Write-Host "Copying files to $InstallDir..."
Copy-Item "$PSScriptRoot\*" -Destination $InstallDir -Recurse -Force

Write-Host "Registering Scheduled Task..."
$taskName = "CourierWindowsWorker"
$scriptPath = "$InstallDir\Courier.exe"
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $InstallDir
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
# Task Scheduler stops a task after 72 hours and does not restart it.
# The worker stays up, restarts after a failure, and never starts a second copy.
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings | Out-Null

Write-Host "Starting the worker..."
try {
    Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
    Write-Host "Courier installed and started for $userId."
} catch {
    Write-Host "Courier installed for $userId. It will start at the next logon."
}
