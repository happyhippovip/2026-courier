param (
    [string]$ServerArg = "",
    [string]$ApiKeyArg = "",
    [string]$WorkerIdArg = "",
    [int]$HealthTimeoutSec = 30
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

# 3. Credential file lives in the user profile, merged with whatever is already there.
Write-Host "`n[3] Configuring Credentials..."
$dataDir = Join-Path $env:LOCALAPPDATA "Courier"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$configPath = Join-Path $dataDir "config.json"

$merged = [ordered]@{}
if (Test-Path -LiteralPath $configPath) {
    try {
        $existing = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    } catch {
        Write-Host "ERROR: Could not read existing configuration at $configPath." -ForegroundColor Red
        exit 1
    }
    foreach ($prop in $existing.PSObject.Properties) {
        $merged[$prop.Name] = $prop.Value
    }
}

$server = [string]$merged["COURIER_SERVER"]
if (-not [string]::IsNullOrWhiteSpace($ServerArg)) {
    $server = $ServerArg
} elseif ([string]::IsNullOrWhiteSpace($server) -or $server -eq "local") {
    $server = Read-Host "Enter COURIER_SERVER URL (e.g. http://192.168.1.100:8080)"
}

$apiKey = [string]$merged["COURIER_API_KEY"]
if (-not [string]::IsNullOrWhiteSpace($ApiKeyArg)) {
    $apiKey = $ApiKeyArg
} elseif ([string]::IsNullOrWhiteSpace($apiKey)) {
    $secureKey = Read-Host "Enter COURIER_API_KEY" -AsSecureString
    $apiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey))
}

$workerId = [string]$merged["WORKER_ID"]
if (-not [string]::IsNullOrWhiteSpace($WorkerIdArg)) {
    $workerId = $WorkerIdArg
} elseif ([string]::IsNullOrWhiteSpace($workerId)) {
    $workerId = "WINDOWS-$($env:COMPUTERNAME)"
}

$merged["WORKER_ID"] = $workerId
$merged["COURIER_SERVER"] = $server
$merged["COURIER_API_KEY"] = $apiKey

$json = $merged | ConvertTo-Json -Depth 6
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($configPath, $json + "`n", $utf8)
Write-Host "Configuration saved to $configPath."

# 4. Service / Start Command
Write-Host "`n[4] Installing Service (Scheduled Task)..."
$installScript = Join-Path $workerDir "install_service.ps1"
if (-not (Test-Path $installScript)) {
    Write-Host "ERROR: install_service.ps1 not found." -ForegroundColor Red
    exit 1
}

Write-Host "Running install_service.ps1..."
$installResult = powershell -ExecutionPolicy Bypass -File $installScript *>&1
$taskSuccess = $?

if (-not $taskSuccess -or $installResult -match "Zugriff verweigert" -or $installResult -match "Access is denied") {
    Write-Host "UAC elevation missing for Scheduled Task. Falling back to background process for current session." -ForegroundColor Yellow
    try {
        $uvPath = (Get-Command "uv" -ErrorAction Stop).Source
        # "call" keeps a quoted path intact. cmd /c strips quotes when the command itself starts with one.
        Start-Process -FilePath $env:ComSpec -ArgumentList "/c call `"$uvPath`" run python daemon.py" -WorkingDirectory $workerDir -WindowStyle Hidden
    } catch {
        Write-Host "Could not start a fallback worker process." -ForegroundColor Yellow
    }
} else {
    Write-Host "Starting the service..."
    Start-ScheduledTask -TaskName "CourierWindowsWorker" -ErrorAction SilentlyContinue
}

# 5. Worker registration & Health confirmation
# daemon.py writes %LOCALAPPDATA%\Courier\logs\daemon.log and does not emit a
# registration-success line. FATAL is the only boot marker in that file.
Write-Host "`n[5] Waiting for Registration & Health Confirmation..."
$logFile = Join-Path $env:LOCALAPPDATA "Courier\logs\daemon.log"
$timeout = $HealthTimeoutSec
if ($timeout -lt 0) { $timeout = 0 }
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$fatalLine = $null
$startLength = 0
if (Test-Path -LiteralPath $logFile) {
    $startLength = (Get-Item -LiteralPath $logFile).Length
}

while ($watch.Elapsed.TotalSeconds -lt $timeout) {
    if (Test-Path -LiteralPath $logFile) {
        $lengthNow = (Get-Item -LiteralPath $logFile).Length
        if ($lengthNow -gt $startLength) {
            $tail = Get-Content -LiteralPath $logFile -Tail 20 -ErrorAction SilentlyContinue
            $hit = @($tail | Where-Object { $_ -match "FATAL" })
            if ($hit.Count -gt 0) {
                $fatalLine = $hit
                break
            }
        }
    }
    Start-Sleep -Seconds 1
}

if ($fatalLine) {
    Write-Host "Worker encountered a fatal error during boot:" -ForegroundColor Red
    $fatalLine | Write-Host
    exit 1
}

Write-Host "[WARNING] Worker health not verified. No registration result is written to $logFile." -ForegroundColor Yellow
exit 2
