param(
    [string]$PackageDir = "$PSScriptRoot\dist",
    [int]$ControllerPort = 18765,
    [int]$HubPort = 18766
)

# Proves a package built by build_package.ps1 starts on the embedded interpreter.
# System Python is removed from PATH. PYTHONPATH and PYTHONHOME are unset.
# The launcher is designed to keep running, so success is controller and hub
# health, then a PID-tree stop that leaves no process whose executable is
# inside this package.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Keep this list equal to $RuntimePackages in build_package.ps1.
$RequiredPackages = @(
    "adapters",
    "courier_core",
    "courier_hub",
    "courier_overlay",
    "courier_runtime",
    "courier_worker"
)

function Show-SmokeLogs([string]$dir) {
    foreach ($name in @("crash.txt", "logs\controller.log", "logs\worker.log", "logs\hub.log")) {
        $path = Join-Path $dir $name
        Write-Host "----- $path -----"
        if (Test-Path -LiteralPath $path) {
            Get-Content -LiteralPath $path -Tail 80
        } else {
            Write-Host "(missing)"
        }
    }
}

function Get-PackageProcesses([string]$rootPrefix) {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and $_.ExecutablePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    })
}

if (-not (Test-Path -LiteralPath $PackageDir)) {
    Write-Error "Package directory missing: $PackageDir"
    exit 1
}
$PackageDir = (Resolve-Path -LiteralPath $PackageDir).Path
$rootPrefix = $PackageDir
if (-not $rootPrefix.EndsWith("\")) { $rootPrefix = $rootPrefix + "\" }

$pythonExe = Join-Path $PackageDir "python\python.exe"
$pthPath = Join-Path $PackageDir "python\python312._pth"
$launcher = Join-Path $PackageDir "Courier.exe"
$libsDir = Join-Path $PackageDir "libs"

foreach ($required in @($pythonExe, $pthPath, $launcher, $libsDir)) {
    if (-not (Test-Path -LiteralPath $required)) {
        Write-Error "Package output missing: $required"
        exit 1
    }
}

$hasPackageRoot = $false
$hasLibs = $false
foreach ($line in @(Get-Content -LiteralPath $pthPath)) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "..") { $hasPackageRoot = $true }
    if ($trimmed -eq "..\libs") { $hasLibs = $true }
}
if (-not $hasPackageRoot -or -not $hasLibs) {
    Write-Host "python312._pth contents:"
    Get-Content -LiteralPath $pthPath | ForEach-Object { Write-Host ("[{0}]" -f $_) }
    Write-Error "python312._pth does not expose the package root and libs"
    exit 1
}

foreach ($pkg in $RequiredPackages) {
    $init = Join-Path $PackageDir "$pkg\__init__.py"
    if (-not (Test-Path -LiteralPath $init)) {
        Write-Error "Staged package missing: $pkg"
        exit 1
    }
}

$libEntries = @(Get-ChildItem -LiteralPath $libsDir -Force)
if ($libEntries.Count -lt 1) {
    Write-Error "libs is empty; dependency install did not populate the package"
    exit 1
}
foreach ($dep in @("flask", "psutil")) {
    if (-not (Test-Path -LiteralPath (Join-Path $libsDir $dep))) {
        Write-Error "libs is missing dependency: $dep"
        exit 1
    }
}

$env:PATH = "$env:SystemRoot\system32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
foreach ($name in @("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "COURIER_HOME", "VIRTUAL_ENV")) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}
$pythonOnPath = Get-Command python -ErrorAction SilentlyContinue
if ($pythonOnPath) {
    Write-Error "system python is still on PATH: $($pythonOnPath.Source)"
    exit 1
}

$versionText = & $pythonExe -c "import sys; print('%d.%d.%d' % sys.version_info[:3]); raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Embedded python is not 3.12.x: $versionText"
    exit 1
}
Write-Host "Embedded Python $versionText"

Push-Location $PackageDir
& $pythonExe -c "import courier_core.serve, courier_worker.host, courier_hub, adapters, courier_overlay, courier_runtime; print('imports-ok')"
$importCode = $LASTEXITCODE
Pop-Location
if ($importCode -ne 0) {
    Write-Error "Embedded interpreter could not import the staged packages"
    exit 1
}

$dataRoot = Join-Path $env:TEMP ("courier-smoke-" + [guid]::NewGuid().ToString("n"))
$dataDir = Join-Path $dataRoot "Courier"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
$configPath = Join-Path $dataDir "config.json"
@{
    COURIER_CONTROLLER_PORT = $ControllerPort
    COURIER_HUB_PORT = $HubPort
} | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding ascii
$env:LOCALAPPDATA = $dataRoot

$proc = $null
$failed = $false
$reason = ""
try {
    $proc = Start-Process -FilePath $launcher -WorkingDirectory $PackageDir -PassThru -WindowStyle Hidden
    Write-Host "Launcher PID $($proc.Id)"

    $deadline = (Get-Date).AddSeconds(60)
    $healthy = $false
    while ((Get-Date) -lt $deadline) {
        $proc.Refresh()
        if ($proc.HasExited) { break }
        $tokenPath = Join-Path $dataDir "run\controller.token"
        if (Test-Path -LiteralPath $tokenPath) {
            $token = (Get-Content -Raw -LiteralPath $tokenPath).Trim()
            if ($token) {
                try {
                    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$ControllerPort/v1/health" -Headers @{"X-Courier-Token" = $token} -UseBasicParsing -TimeoutSec 3
                    if ($resp.StatusCode -eq 200) {
                        $healthy = $true
                        break
                    }
                } catch {
                    Write-Host "controller not ready: $($_.Exception.Message)"
                }
            }
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $healthy) {
        throw "controller did not become healthy on 127.0.0.1:$ControllerPort"
    }
    Write-Host "Controller healthy"

    $hubDeadline = (Get-Date).AddSeconds(30)
    $hubRunning = $false
    while ((Get-Date) -lt $hubDeadline) {
        $proc.Refresh()
        if ($proc.HasExited) { break }
        try {
            $hub = Invoke-WebRequest -Uri "http://127.0.0.1:$HubPort/hub/api/status" -UseBasicParsing -TimeoutSec 3
            if ($hub.StatusCode -eq 200) {
                $status = $hub.Content | ConvertFrom-Json
                if ($status.controller -eq "running") {
                    $hubRunning = $true
                    break
                }
                Write-Host "hub status controller=$($status.controller)"
            }
        } catch {
            Write-Host "hub not ready: $($_.Exception.Message)"
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $hubRunning) {
        throw "hub did not report the controller running on 127.0.0.1:$HubPort"
    }
    Write-Host "Hub reports controller running"

    $seen = 0
    for ($i = 0; $i -lt 10; $i++) {
        $pythonPath = (Resolve-Path -LiteralPath $pythonExe).Path
        $seen = @(Get-PackageProcesses $rootPrefix | Where-Object { $_.ExecutablePath -eq $pythonPath }).Count
        if ($seen -ge 3) { break }
        Start-Sleep -Milliseconds 500
    }
    if ($seen -lt 3) {
        throw "expected embedded python for controller, worker, and hub; saw $seen"
    }
    Write-Host "Embedded python processes: $seen"
} catch {
    $failed = $true
    $reason = "$_"
    Write-Host "SMOKE FAIL: $reason"
} finally {
    if ($proc) {
        $proc.Refresh()
        if (-not $proc.HasExited) {
            $ErrorActionPreference = "Continue"
            & taskkill.exe /F /T /PID $proc.Id | Out-Host
            $ErrorActionPreference = "Stop"
        }
    }
    Start-Sleep -Seconds 3
    $left = @(Get-PackageProcesses $rootPrefix)
    if ($left.Count -gt 0) {
        foreach ($alive in $left) {
            Write-Host "survivor $($alive.ProcessId) $($alive.ExecutablePath)"
            Stop-Process -Id $alive.ProcessId -Force -ErrorAction SilentlyContinue
        }
        $failed = $true
        if (-not $reason) {
            $reason = "$($left.Count) package process(es) survived the launcher stop"
        }
    }
}

if ($failed) {
    if ($dataDir) { Show-SmokeLogs $dataDir }
    Write-Error $reason
    exit 1
}

Write-Host "SMOKE PASS"
exit 0
