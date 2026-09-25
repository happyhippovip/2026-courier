<#
.SYNOPSIS
  Open the live Google Antigravity UI: find it, never start a second copy,
  and open only a port that answers over HTTPS right now.

.DESCRIPTION
  1. Looks for running Antigravity.exe / language_server*.exe processes.
  2. Starts Antigravity once with the proven flags (--disable-gpu
     --disable-gpu-sandbox) only if no Antigravity.exe runs. -NoStart skips it.
  3. Collects candidate ports: 127.0.0.1 listeners owned by those processes,
     ordered by the most recent URLs in %APPDATA%\Antigravity\logs\main.log.
     A port from the log is only a hint; it must also be listening now.
  4. Probes each candidate with curl.exe -k (local self-signed certificate)
     and opens the first one that answers HTTP 200.
  5. Otherwise prints ANTIGRAVITY_UI_NOT_FOUND and exits 2.

  It never hard-codes a port, never changes settings (confirmations stay as
  they are), never deletes profiles, credentials or updater files, and never
  stops any process.

  -InstallShortcut creates the Desktop shortcut "Google Antigravity öffnen".
#>
[CmdletBinding()]
param(
    [switch]$NoStart,
    [switch]$InstallShortcut,
    [int]$StartWaitSeconds = 90
)

$ErrorActionPreference = 'Stop'
$Exe = Join-Path $env:LOCALAPPDATA 'Programs\antigravity\Antigravity.exe'
$MainLog = Join-Path $env:APPDATA 'Antigravity\logs\main.log'

function Get-AntigravityPids {
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'Antigravity.exe' OR Name LIKE 'language_server%'"
    [pscustomobject]@{
        Main           = @($procs | Where-Object { $_.Name -eq 'Antigravity.exe' -and $_.CommandLine -notmatch '--type=' })
        All            = @($procs | ForEach-Object { [int]$_.ProcessId })
        LanguageServer = @($procs | Where-Object { $_.Name -like 'language_server*' })
    }
}

function Get-LogPorts {
    # Most recent first; only a hint for ordering.
    if (-not (Test-Path $MainLog)) { return @() }
    $hits = @(Select-String -Path $MainLog -Pattern 'https?://127\.0\.0\.1:(\d{2,5})' -AllMatches |
        ForEach-Object { $_.Matches } | ForEach-Object { [int]$_.Groups[1].Value })
    if (-not $hits) { return @() }
    [array]::Reverse($hits)
    $hits | Select-Object -Unique
}

function Get-ListeningPorts([int[]]$Pids) {
    if (-not $Pids) { return @() }
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -in @('127.0.0.1', '::1', '0.0.0.0') -and $_.OwningProcess -in $Pids } |
        ForEach-Object { [int]$_.LocalPort } | Select-Object -Unique
}

function Test-HttpsPort([int]$Port) {
    $code = & curl.exe -k -s -o NUL -w '%{http_code}' --max-time 4 "https://127.0.0.1:$Port/" 2>$null
    return ($code -eq '200')
}

if ($InstallShortcut) {
    $name = 'Google Antigravity ' + [char]0x00F6 + 'ffnen.lnk'
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) $name))
    $lnk.TargetPath = Join-Path $PSHOME 'powershell.exe'
    $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $lnk.IconLocation = "$Exe,0"
    $lnk.Save()
    Write-Output "SHORTCUT_CREATED=$name"
    return
}

$state = Get-AntigravityPids
if (-not $state.Main) {
    if ($NoStart) { Write-Output 'ANTIGRAVITY_NOT_RUNNING'; exit 3 }
    if (-not (Test-Path $Exe)) { Write-Output "ANTIGRAVITY_EXE_NOT_FOUND=$Exe"; exit 4 }
    Write-Output 'STARTING_ANTIGRAVITY=--disable-gpu --disable-gpu-sandbox'
    Start-Process -FilePath $Exe -ArgumentList '--disable-gpu', '--disable-gpu-sandbox'
} else {
    Write-Output "ANTIGRAVITY_RUNNING=$($state.Main.ProcessId -join ',')"
}

$deadline = (Get-Date).AddSeconds($StartWaitSeconds)
do {
    $state = Get-AntigravityPids
    $listening = @(Get-ListeningPorts $state.All)
    $logPorts = @(Get-LogPorts)
    $ordered = @($logPorts | Where-Object { $_ -in $listening }) + @($listening | Where-Object { $_ -notin $logPorts })
    foreach ($port in $ordered) {
        if (Test-HttpsPort $port) {
            Write-Output "LANGUAGE_SERVER_RUNNING=$([bool]$state.LanguageServer)"
            Write-Output "LIVE_UI_PORT=$port"
            Start-Process "https://127.0.0.1:$port/"
            exit 0
        }
    }
    Start-Sleep -Seconds 3
} while ((Get-Date) -lt $deadline)

Write-Output "CANDIDATE_PORTS=$($ordered -join ',')"
Write-Output 'ANTIGRAVITY_UI_NOT_FOUND'
exit 2
