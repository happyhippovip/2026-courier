#Requires -Version 5.1
<#
  Muse CLI probe. Verifies on THIS machine (never guesses):
  - exact muse command found on PATH (Get-Command muse)
  - `muse --help` exit code + output excerpt
  - whether `--yolo` is really supported (literal `--yolo` token in help text)

  Writes: <repo>/runtime/muse_probe.json (machine fact, fail-closed).
  Never launches a session: only `muse --help` is executed, with a timeout.
#>
param(
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'

$wallDir = $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $wallDir)
$probePath = Join-Path $repoRoot 'runtime\muse_probe.json'

$probe = [ordered]@{
    muse_command   = $null
    muse_source    = $null
    help_ok        = $false
    help_exit      = $null
    yolo_supported = $false
    probed_at      = ([DateTime]::UtcNow.ToString('o'))
    host           = $env:COMPUTERNAME
    error          = $null
}

function Write-Probe {
    $dir = Split-Path -Parent $probePath
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $tmp = "$probePath.tmp"
    ($probe | ConvertTo-Json -Depth 4) | Out-File -FilePath $tmp -Encoding utf8 -Force
    Move-Item -Force -Path $tmp -Destination $probePath
}

$muse = Get-Command muse -ErrorAction SilentlyContinue
if (-not $muse) {
    $probe.error = 'muse not found on PATH (Get-Command muse returned nothing).'
    Write-Probe
    throw $probe.error
}
$probe.muse_command = 'muse'
$probe.muse_source = $muse.Source

$job = Start-Job -ScriptBlock {
    param($exe)
    & $exe --help 2>&1 | Out-String
} -ArgumentList $muse.Source

$finished = Wait-Job -Job $job -Timeout $TimeoutSeconds
if (-not $finished) {
    Stop-Job -Job $job -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $job -Force -ErrorAction SilentlyContinue | Out-Null
    $probe.error = "muse --help timed out after $TimeoutSeconds seconds."
    Write-Probe
    throw $probe.error
}

$output = Receive-Job -Job $job
$jobState = [string]$job.State
Remove-Job -Job $job -Force -ErrorAction SilentlyContinue | Out-Null
if ($null -eq $output) { $output = '' }
$text = [string]$output

# Help is OK only when the job completed AND returned non-empty text that
# does not look like an error. help_exit mirrors job completion (0/1);
# the child process exit code is not observable through the job channel.
$probe.help_exit = if ($jobState -eq 'Completed') { 0 } else { 1 }
$probe.help_ok = ($jobState -eq 'Completed') -and ($text.Trim().Length -gt 0)
if ($text -match '(?i)is not recognized|command not found|unexpected argument') {
    $probe.help_ok = $false
}

# YOLO is supported only if the REAL help text on THIS machine lists it.
if ($text -match '--yolo\b') {
    $probe.yolo_supported = $true
}

$probe.help_excerpt = $text.Substring(0, [Math]::Min(2000, $text.Length))

Write-Probe

if (-not $probe.help_ok) {
    throw 'muse --help did not return usable help text. See runtime/muse_probe.json.'
}

Write-Output ("MUSE_COMMAND=muse SOURCE={0} YOLO_SUPPORTED={1}" -f $probe.muse_source, $probe.yolo_supported)
