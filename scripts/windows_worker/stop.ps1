# Stops the Courier launcher of this user and only its own process tree.
#
# The launcher records its PID in <home>\run\launcher.pid. This script asks
# the controller to shut down, then ends that PID and its children. It never
# stops a process by image name, so another program called Courier.exe keeps
# running. Exit code 0: stopped or nothing was running. Exit code 1: a process
# of the owned tree is still alive.
param(
    [string]$CourierHome = $(if ($env:COURIER_HOME) { $env:COURIER_HOME } else { Join-Path $env:LOCALAPPDATA "Courier" }),
    [int]$WaitSeconds = 10
)

$pidFile = Join-Path $CourierHome "run\launcher.pid"
if (-not (Test-Path $pidFile)) {
    Write-Host "Courier is not running (no $pidFile)."
    exit 0
}

$launcherPid = 0
if (-not [int]::TryParse((Get-Content $pidFile -Raw).Trim(), [ref]$launcherPid)) {
    Write-Host "Ignoring unreadable PID file $pidFile."
    Remove-Item -Force $pidFile
    exit 0
}

$launcher = Get-Process -Id $launcherPid -ErrorAction SilentlyContinue
if ($null -eq $launcher -or $launcher.ProcessName -ne "Courier") {
    # The PID is gone or now belongs to another program: leave it alone.
    Write-Host "Courier is not running (stale PID $launcherPid)."
    Remove-Item -Force $pidFile
    exit 0
}

function Get-OwnedTree([int]$rootPid) {
    $all = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
    $owned = @($rootPid)
    $frontier = @($rootPid)
    while ($frontier.Count -gt 0) {
        $children = @($all | Where-Object { $frontier -contains $_.ParentProcessId -and $owned -notcontains $_.ProcessId } |
            ForEach-Object { [int]$_.ProcessId })
        $owned += $children
        $frontier = $children
    }
    return $owned
}

$owned = Get-OwnedTree $launcherPid
# Hold a handle on each owned process now, so a PID reused after exit is
# never mistaken for one of ours.
$procs = @($owned | ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue } | Where-Object { $null -ne $_ })
foreach ($p in $procs) { try { $null = $p.Handle } catch { } }
Write-Host "Stopping Courier (launcher PID $launcherPid, $($owned.Count) processes)..."

# Graceful first: the controller closes its journal before it exits.
$configPath = Join-Path $CourierHome "config.json"
$tokenPath = Join-Path $CourierHome "run\controller.token"
$port = 8765
if (Test-Path $configPath) {
    try {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        if ($config.COURIER_CONTROLLER_PORT) { $port = [int]$config.COURIER_CONTROLLER_PORT }
    } catch { }
}
if (Test-Path $tokenPath) {
    try {
        $token = (Get-Content $tokenPath -Raw).Trim()
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$port/v1/shutdown" -Headers @{ "X-Courier-Token" = $token } -TimeoutSec 3 | Out-Null
        Start-Sleep -Seconds 1
    } catch {
        Write-Host "Graceful shutdown not answered; stopping the process tree."
    }
}

# The launcher would restart the controller, so end the whole owned tree.
& taskkill.exe /T /F /PID $launcherPid 2>&1 | Out-Null
foreach ($p in $procs) {
    if (-not $p.HasExited) { try { $p.Kill() } catch { } }
}

$deadline = (Get-Date).AddSeconds($WaitSeconds)
do {
    $alive = @($procs | Where-Object { -not $_.HasExited } | ForEach-Object { $_.Id })
    if ($alive.Count -eq 0) { break }
    Start-Sleep -Milliseconds 250
} while ((Get-Date) -lt $deadline)

if ($alive.Count -gt 0) {
    Write-Host "ERROR: Courier processes still running: $($alive -join ', ')" -ForegroundColor Red
    exit 1
}

Remove-Item -Force $pidFile -ErrorAction SilentlyContinue
Write-Host "Courier stopped."
exit 0
