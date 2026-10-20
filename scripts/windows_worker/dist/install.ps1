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

function Test-CourierInstallHealth {
    param(
        [string]$Token,
        [int]$Port = 8765,
        [int]$TimeoutSeconds = 20
    )
    # The launcher serves the controller on this PC. Task Scheduler accepting
    # the start is not the same as Courier being ready.
    if ([string]::IsNullOrWhiteSpace($Token) -or $Port -lt 1 -or $TimeoutSeconds -lt 1) { return $false }
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($true) {
        $res = $null
        try {
            $req = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$Port/v1/health")
            $req.Timeout = 1000
            $req.Headers.Add("X-Courier-Token", $Token)
            $res = $req.GetResponse()
            if ([int]$res.StatusCode -eq 200) { return $true }
        } catch {
        } finally {
            if ($res) { $res.Close() }
        }
        if ($watch.Elapsed.TotalSeconds -ge $TimeoutSeconds) { return $false }
        Start-Sleep -Seconds 1
    }
}
# end Test-CourierInstallHealth

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
    Remove-Item -LiteralPath $tokenPath -Force -ErrorAction SilentlyContinue
    Write-Host "ERROR: could not restrict access to the controller token. The token was removed." -ForegroundColor Red
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
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Write-Host "ERROR: the previous scheduled task is still present: $taskName" -ForegroundColor Red
        exit 1
    }
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $InstallDir
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
# Task Scheduler stops a task after 72 hours and does not restart it.
# The worker stays up, restarts after a failure, and never starts a second copy.
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable -MultipleInstances IgnoreNew
try {
    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings -ErrorAction Stop | Out-Null
} catch {
    Write-Host "ERROR: the scheduled task could not be registered for $userId." -ForegroundColor Red
    exit 1
}
$registeredTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $registeredTask -or $registeredTask.Principal.UserId -ne $userId) {
    Write-Host "ERROR: the scheduled task could not be registered for $userId." -ForegroundColor Red
    exit 1
}

Write-Host "Starting the worker..."
$startedNow = $false
try {
    Start-ScheduledTask -TaskName $taskName -ErrorAction Stop
    $startedNow = $true
} catch {
    Write-Host "Courier installed for $userId. It will start at the next logon."
}
if ($startedNow) {
    $ready = Test-CourierInstallHealth -Token $ApiKey -Port 8765 -TimeoutSeconds 20
    if ($ready) {
        Write-Host "Courier installed and started for $userId."
    } else {
        Write-Host "ERROR: Courier is installed for $userId, but it is not ready yet. It will try again at the next logon." -ForegroundColor Red
        exit 1
    }
}
