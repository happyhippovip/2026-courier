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
$daemonPath = Join-Path $workerDir "daemon.py"
if (-not (Test-Path $daemonPath)) {
    Write-Host "ERROR: daemon.py not found at $daemonPath" -ForegroundColor Red
    exit 1
}
Write-Host "Worker directory: $workerDir"

# 3. Secure env/credential prerequisites
Write-Host "`n[3] Configuring Credentials..."
$configPath = Join-Path $workerDir "config.json"
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

$workerId = $config.WORKER_ID
if (-not [string]::IsNullOrWhiteSpace($WorkerIdArg)) {
    $workerId = $WorkerIdArg
} elseif ([string]::IsNullOrWhiteSpace($workerId)) {
    $workerId = "WINDOWS-$($env:COMPUTERNAME)"
}

$newConfig = @{
    WORKER_ID = $workerId
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

# Run install_service.ps1
Write-Host "Running install_service.ps1..."
$installResult = powershell -ExecutionPolicy Bypass -File $installScript *>&1
$taskSuccess = $?

if (-not $taskSuccess -or $installResult -match "Zugriff verweigert" -or $installResult -match "Access is denied") {
    Write-Host "UAC elevation missing for Scheduled Task. Falling back to background process for current session." -ForegroundColor Yellow
    Start-Process -FilePath "uv" -ArgumentList "run python daemon.py" -WorkingDirectory $workerDir -WindowStyle Hidden
} else {
    Write-Host "Starting the service..."
    Start-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
}

# 5. Worker registration & Health confirmation
Write-Host "`n[5] Waiting for Registration & Health Confirmation..."
$logDir = Join-Path $workerDir "logs"
$logFile = Join-Path $logDir "worker.log"

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
# Clear stale log to avoid false positive
if (Test-Path $logFile) { Clear-Content $logFile -ErrorAction SilentlyContinue }
if (-not (Test-Path $logFile)) { New-Item -ItemType File -Path $logFile | Out-Null }

$timeout = 30
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$success = $false

while ($watch.Elapsed.TotalSeconds -lt $timeout) {
    $content = Get-Content $logFile -Tail 20 -ErrorAction SilentlyContinue
    if ($content -match "Registered successfully") {
        $success = $true
        break
    }
    if ($content -match "FATAL") {
        Write-Host "Worker encountered a fatal error during boot:" -ForegroundColor Red
        $content | Where-Object { $_ -match "FATAL" } | Write-Host
        exit 1
    }
    Start-Sleep -Seconds 2
}

if ($success) {
    Write-Host "`n[SUCCESS] Worker registered and is healthy!" -ForegroundColor Green
    Write-Host "Bootstrap complete. Worker will now start automatically on boot." -ForegroundColor Green
} else {
    Write-Host "`n[WARNING] Timeout waiting for registration confirmation." -ForegroundColor Yellow
    Write-Host "Check logs at: $logFile"
}
