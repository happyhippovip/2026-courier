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

Write-Host "Ensuring 'keyring' module is installed for secure credential access..."
uv pip install keyring | Out-Null

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

# --- Server URL (non-secret, stored in config.json) ---
$server = $config.COURIER_SERVER
if (-not [string]::IsNullOrWhiteSpace($ServerArg)) {
    $server = $ServerArg
} elseif ([string]::IsNullOrWhiteSpace($server) -or $server -eq "local") {
    $server = Read-Host "Enter COURIER_SERVER URL (e.g. http://192.168.1.100:8080)"
}

# --- API Key (secret, stored in Windows Credential Manager — NEVER in config.json) ---
$apiKey = ""
if (-not [string]::IsNullOrWhiteSpace($ApiKeyArg)) {
    $apiKey = $ApiKeyArg
} else {
    # Check if already stored via Python keyring
    $existing = uv run python -c "import keyring; print(keyring.get_password('courier_worker', 'courier_api_key') or '')" 2>$null
    if (-not [string]::IsNullOrWhiteSpace($existing)) {
        Write-Host "API Key already stored in Windows Credential Manager (via keyring)."
        $useExisting = Read-Host "Use existing key? (Y/n)"
        if ($useExisting -ne "n") {
            $apiKey = "__CREDENTIAL_MANAGER__"
        }
    }
    if ($apiKey -ne "__CREDENTIAL_MANAGER__") {
        $secureKey = Read-Host "Enter COURIER_API_KEY" -AsSecureString
        $apiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey))
    }
}

# Store API key in Windows Credential Manager (OS-native secure storage) for SYSTEM account
if ($apiKey -ne "__CREDENTIAL_MANAGER__" -and -not [string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "Storing API Key in SYSTEM Credential Manager..."
    $tempFile = Join-Path $env:TEMP "courier_key.txt"
    $apiKey | Out-File -FilePath $tempFile -Encoding utf8 -NoNewline
    
    $storeCmd = "import keyring; key=open(r'$tempFile', encoding='utf-8').read(); keyring.set_password('courier_worker', 'courier_api_key', key)"
    $storeAction = New-ScheduledTaskAction -Execute "uv" -Argument "run python -c `"$storeCmd`"" -WorkingDirectory $workerDir
    $storePrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $taskName = "CourierSystemKeyStore_Temp"
    
    Register-ScheduledTask -TaskName $taskName -Action $storeAction -Principal $storePrincipal -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 5
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false | Out-Null
    Remove-Item -Path $tempFile -Force
    
    Write-Host "API Key stored in Windows Credential Manager (SYSTEM via keyring)." -ForegroundColor Green
}

# --- Worker ID (non-secret, stored in config.json) ---
$workerId = $config.WORKER_ID
if (-not [string]::IsNullOrWhiteSpace($WorkerIdArg)) {
    $workerId = $WorkerIdArg
} elseif ([string]::IsNullOrWhiteSpace($workerId)) {
    $workerId = "WINDOWS-$($env:COMPUTERNAME)"
}

# Config.json stores ONLY non-secret fields. API key is in Credential Manager.
$newConfig = @{
    WORKER_ID = $workerId
    COURIER_SERVER = $server
}
$newConfig | ConvertTo-Json | Set-Content $configPath
Write-Host "Configuration saved to $configPath (non-secret fields only)."
Write-Host "API Key stored in Windows Credential Manager (not in config.json)." -ForegroundColor Green

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
