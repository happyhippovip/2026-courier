param (
    [string]$ServerArg = "",
    [string]$ApiKeyArg = "",
    [string]$WorkerIdArg = ""
)

$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-Not $IsAdmin) {
    Write-Host "WARNING: Not running as Administrator. Scheduled Task will not be registered." -ForegroundColor Yellow
}

$canWriteProgramFiles = $false
if ($env:ProgramFiles -and (Test-Path $env:ProgramFiles)) {
    try {
        $testFile = Join-Path $env:ProgramFiles ".courier_write_test_$([guid]::NewGuid().ToString('N'))"
        [IO.File]::WriteAllText($testFile, "test")
        [IO.File]::Delete($testFile)
        $canWriteProgramFiles = $true
    } catch {
        $canWriteProgramFiles = $false
    }
}

$InstallDir = if ($env:COURIER_INSTALL_DIR) {
    $env:COURIER_INSTALL_DIR
} elseif ($IsAdmin -or $canWriteProgramFiles) {
    "$env:ProgramFiles\CourierWorker"
} else {
    "$env:LOCALAPPDATA\CourierWorker"
}
$DataDir = "$env:LOCALAPPDATA\Courier"
$ConfigPath = Join-Path $DataDir "config.json"

Write-Host "========================================"
Write-Host " Courier Windows Worker Installer"
Write-Host "========================================"

try {
    New-Item -ItemType Directory -Force -Path $DataDir -ErrorAction Stop | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $DataDir "run") -ErrorAction Stop | Out-Null
    New-Item -ItemType Directory -Force -Path $InstallDir -ErrorAction Stop | Out-Null
} catch {
    Write-Error "Courier install not proven: directories could not be created."
    exit 1
}

$Server = $ServerArg
$ApiKey = $ApiKeyArg
$WorkerId = $WorkerIdArg

$configObj = @{}
if (Test-Path $ConfigPath) {
    Write-Host "Found existing configuration."
    try {
        $raw = Get-Content $ConfigPath -Raw | ConvertFrom-Json
        if ($raw) {
            foreach ($prop in $raw.PSObject.Properties) {
                $configObj[$prop.Name] = $prop.Value
            }
        }
    } catch {}
    if (-not $Server -and $configObj.ContainsKey("COURIER_SERVER")) { $Server = $configObj["COURIER_SERVER"] }
    if (-not $ApiKey) {
        $tokenPath = Join-Path $DataDir "run\controller.token"
        if (Test-Path $tokenPath) {
            $ApiKey = Get-Content $tokenPath
        }
    }
    if (-not $WorkerId -and $configObj.ContainsKey("COURIER_WORKER_ID")) { $WorkerId = $configObj["COURIER_WORKER_ID"] }
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

$configObj["COURIER_SERVER"] = $Server
$configObj["COURIER_WORKER_ID"] = $WorkerId
$configObj | ConvertTo-Json | Set-Content $ConfigPath

$tokenPath = Join-Path $DataDir "run\controller.token"
$ApiKey | Set-Content $tokenPath -NoNewline

Write-Host "Configuration saved to $ConfigPath."
Write-Host "Token saved to $tokenPath."

Write-Host "Copying files to $InstallDir..."
try {
    Copy-Item "$PSScriptRoot\*" -Destination $InstallDir -Recurse -Force -ErrorAction Stop
} catch {
    Write-Error "Courier install not proven: files were not copied."
    exit 1
}
if (-not (Test-Path -LiteralPath $InstallDir)) {
    Write-Error "Courier install not proven: install directory is missing."
    exit 1
}

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
    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal | Out-Null

    Write-Host "Starting Service..."
    Start-ScheduledTask -TaskName $taskName
} else {
    Write-Host "Skipped Scheduled Task registration (requires Administrator)." -ForegroundColor Yellow
}

$InstalledExe = Join-Path $InstallDir "Courier.exe"
if (-not (Test-Path -LiteralPath $InstalledExe)) {
    Write-Error "Courier install not proven: Courier.exe is missing."
    exit 1
}

Write-Host "Courier installed successfully!"
