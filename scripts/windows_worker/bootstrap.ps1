param (
    [string]$ServerArg = "",
    [string]$ApiKeyArg = "",
    [string]$WorkerIdArg = ""
)

Write-Host "========================================"
Write-Host " Courier Windows Worker Bootstrap"
Write-Host "========================================"

# 1. Runtime / Package Installation Check
Write-Host "`n[1] Checking Runtime Prerequisites..."
Write-Host "Courier.exe is the worker. A separate Python toolchain is not required."

# 2. Exact repo/start path
Write-Host "`n[2] Verifying Paths..."
$workerDir = $PSScriptRoot
$daemonPath = Join-Path $workerDir "Courier.exe"
if (-not (Test-Path $daemonPath)) {
    Write-Host "ERROR: Courier.exe not found at $daemonPath" -ForegroundColor Red
    exit 1
}
Write-Host "Worker directory: $workerDir"

# 3. Secure env/credential prerequisites
Write-Host "`n[3] Configuring Credentials..."
function Test-CanPrompt {
    try {
        return [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
    } catch {
        return $false
    }
}

if ($env:LOCALAPPDATA) {
    $dataDir = Join-Path $env:LOCALAPPDATA "Courier"
} else {
    $dataDir = Join-Path $env:ProgramData "CourierWorker"
}
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataDir "run") | Out-Null
$configPath = Join-Path $dataDir "config.json"
$tokenPath = Join-Path $dataDir "run\controller.token"
$config = @{}
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
}

$server = $config.COURIER_SERVER
if (-not [string]::IsNullOrWhiteSpace($ServerArg)) {
    $server = $ServerArg
} elseif ([string]::IsNullOrWhiteSpace($server) -or $server -eq "local") {
    if (-not (Test-CanPrompt)) {
        Write-Host "ERROR: a Courier server URL is required. Pass -ServerArg." -ForegroundColor Red
        exit 1
    }
    $server = Read-Host "Enter COURIER_SERVER URL (for example http://127.0.0.1:8080)"
}
if ([string]::IsNullOrWhiteSpace($server)) {
    Write-Host "ERROR: a Courier server URL is required. Pass -ServerArg." -ForegroundColor Red
    exit 1
}

$apiKey = ""
if (Test-Path $tokenPath) { $apiKey = (Get-Content -LiteralPath $tokenPath -Raw).Trim() }
if ([string]::IsNullOrWhiteSpace($apiKey)) { $apiKey = [string]$config.COURIER_API_KEY }
if (-not [string]::IsNullOrWhiteSpace($ApiKeyArg)) {
    $apiKey = $ApiKeyArg
} elseif ([string]::IsNullOrWhiteSpace($apiKey)) {
    if (-not (Test-CanPrompt)) {
        Write-Host "ERROR: a Courier API key is required. Pass -ApiKeyArg." -ForegroundColor Red
        exit 1
    }
    $secureKey = Read-Host "Enter COURIER_API_KEY" -AsSecureString
    $apiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey))
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "ERROR: a Courier API key is required. Pass -ApiKeyArg." -ForegroundColor Red
    exit 1
}
if ($apiKey.Length -lt 32) {
    Write-Host "ERROR: the API key must be at least 32 characters. Pass -ApiKeyArg." -ForegroundColor Red
    exit 1
}

$workerId = $config.COURIER_WORKER_ID
if (-not [string]::IsNullOrWhiteSpace($WorkerIdArg)) {
    $workerId = $WorkerIdArg
} elseif ([string]::IsNullOrWhiteSpace($workerId)) {
    $workerId = "WINDOWS-$($env:COMPUTERNAME)"
}

$newConfig = @{
    COURIER_WORKER_ID = $workerId
    COURIER_SERVER = $server
}
$newConfig | ConvertTo-Json | Set-Content $configPath
$apiKey | Set-Content -LiteralPath $tokenPath -NoNewline
$ownerSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls $tokenPath /inheritance:r /grant:r "*${ownerSid}:(R)" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $tokenPath -Force -ErrorAction SilentlyContinue
    Write-Host "ERROR: could not restrict access to the controller token. The token was removed." -ForegroundColor Red
    exit 1
}
Write-Host "Configuration saved to $configPath. The API key is in the controller token, not in config.json."

# 4. Service / Start Command
Write-Host "`n[4] Installing Service (Scheduled Task)..."
$installScript = Join-Path $workerDir "install_service.ps1"
if (-not (Test-Path $installScript)) {
    Write-Host "ERROR: install_service.ps1 not found." -ForegroundColor Red
    exit 1
}

# The task runs as the signed-in user at logon. It does not ask for a higher privilege.
Write-Host "Running install_service.ps1..."
. (Join-Path $PSScriptRoot "confirm_daemon.ps1")
$logDir = Join-Path $dataDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "daemon.log"
$logStart = [int64]0
if (Test-Path -LiteralPath $logFile) { $logStart = (Get-Item -LiteralPath $logFile).Length }

$installResult = powershell -ExecutionPolicy Bypass -File $installScript *>&1
$taskSuccess = $?
$proc = $null

if (-not $taskSuccess -or $installResult -match "Zugriff verweigert" -or $installResult -match "Access is denied") {
    Write-Host "The scheduled task could not be registered. Starting Courier for this sign-in only." -ForegroundColor Yellow
    $proc = Start-Process -FilePath $daemonPath -WorkingDirectory $workerDir -WindowStyle Hidden -PassThru
    $stamp = ""
    try { $stamp = $proc.StartTime.ToUniversalTime().ToString("o") } catch { $stamp = "" }
    @($proc.Id, $stamp) | Out-File -FilePath "$workerDir\worker.pid" -Encoding ascii
} else {
    Write-Host "Starting the service..."
    Start-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
}

# 5. Confirm the daemon started. An empty log is not a healthy worker.
Write-Host "`n[5] Waiting until the worker reports that it started..."
$controllerPort = 8765
if ($config.COURIER_CONTROLLER_PORT) {
    $parsedPort = 0
    if ([int]::TryParse([string]$config.COURIER_CONTROLLER_PORT, [ref]$parsedPort) -and $parsedPort -gt 0) {
        $controllerPort = $parsedPort
    }
}
$started = Wait-CourierDaemon -LogFile $logFile -LogStart $logStart -Process $proc -TimeoutSeconds 20 -Token $apiKey -ControllerPort $controllerPort
if (-not $started) {
    Write-Host "ERROR: Courier did not start. Check $logFile" -ForegroundColor Red
    exit 1
}
Write-Host "Courier started." -ForegroundColor Green
Write-Host "Bootstrap complete." -ForegroundColor Green
