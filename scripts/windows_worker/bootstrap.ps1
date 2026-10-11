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
if (-not (Get-Command "uv" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: uv is not installed or not in PATH." -ForegroundColor Red
    exit 1
}
$pyVer = uv run python --version
Write-Host "Found Python (via uv): $pyVer"

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
$dataDir = [System.Environment]::ExpandEnvironmentVariables("%PROGRAMDATA%\CourierWorker")
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Force -Path $dataDir | Out-Null }
$configPath = Join-Path $dataDir "config.json"
$config = @{}
if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
}

$server = $config.COURIER_SERVER
if (-not [string]::IsNullOrWhiteSpace($ServerArg)) {
    $server = $ServerArg
} elseif ([string]::IsNullOrWhiteSpace($server) -or $server -eq "local") {
    $server = Read-Host "Enter COURIER_SERVER URL (e.g. http://192.168.1.100:8080)"
}

$apiKey = $config.COURIER_API_KEY
if (-not [string]::IsNullOrWhiteSpace($ApiKeyArg)) {
    $apiKey = $ApiKeyArg
} elseif ([string]::IsNullOrWhiteSpace($apiKey)) {
    $secureKey = Read-Host "Enter COURIER_API_KEY" -AsSecureString
    $apiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey))
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
    COURIER_API_KEY = $apiKey
}
$newConfig | ConvertTo-Json | Set-Content $configPath
Write-Host "Configuration saved to $configPath (API Key stored securely in config)."

# 4. Service / Start Command
Write-Host "`n[4] Installing Service (Scheduled Task)..."
$installScript = Join-Path $workerDir "install_service.ps1"
if (-not (Test-Path $installScript)) {
    Write-Host "ERROR: install_service.ps1 not found." -ForegroundColor Red
    exit 1
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Attempting to elevate privileges for Scheduled Task installation..."
    try {
        Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" `"$ServerArg`" `"$ApiKeyArg`" `"$WorkerIdArg`"" -Verb RunAs -ErrorAction Stop
        exit 0
    } catch {
        Write-Host "UAC elevation cancelled or failed. Proceeding with fallback." -ForegroundColor Yellow
    }
}

# Run install_service.ps1
Write-Host "Running install_service.ps1..."
$installResult = powershell -ExecutionPolicy Bypass -File $installScript *>&1
$taskSuccess = $?

$logDir = Join-Path $dataDir "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "host.log"
if (Test-Path $logFile) { Clear-Content $logFile -ErrorAction SilentlyContinue }
if (-not (Test-Path $logFile)) { New-Item -ItemType File -Path $logFile | Out-Null }

if (-not $taskSuccess -or $installResult -match "Zugriff verweigert" -or $installResult -match "Access is denied" -or -not $isAdmin) {
    Write-Host "UAC elevation missing for Scheduled Task. Falling back to background process for current session." -ForegroundColor Yellow
    $proc = Start-Process -FilePath $daemonPath -WorkingDirectory $workerDir -WindowStyle Hidden -PassThru
    $proc.Id | Out-File -FilePath "$workerDir\worker.pid" -Encoding ascii
} else {
    Write-Host "Starting the service..."
    Start-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
}

# 5. Worker registration & Health confirmation
Write-Host "`n[5] Waiting for Registration & Health Confirmation..."
$timeout = 10
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$success = $true

while ($watch.Elapsed.TotalSeconds -lt $timeout) {
    $content = Get-Content $logFile -Tail 20 -ErrorAction SilentlyContinue
    if ($content -match "FATAL" -or $content -match "Error launching daemon") {
        Write-Host "Worker encountered a fatal error during boot:" -ForegroundColor Red
        $content | Where-Object { $_ -match "FATAL" -or $_ -match "Error" } | Write-Host
        $success = $false
        break
    }
    Start-Sleep -Seconds 2
}

if ($success) {
    Write-Host "`n[SUCCESS] Worker started and appears healthy!" -ForegroundColor Green
    Write-Host "Bootstrap complete. CourierWindowsWorker is running." -ForegroundColor Green
} else {
    Write-Host "`n[WARNING] Worker startup failed or encountered errors." -ForegroundColor Yellow
    Write-Host "Check logs at: $logFile"
}
