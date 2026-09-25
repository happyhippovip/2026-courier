#Requires -Version 5.1
<#
  Muse Wall visual launcher.

  Root cause fixed 2026-09-24 (OBSERVED in this file, rev before fix):
  the old version built ONE command string with quoted subcommand names
  and chained panes with a bare semicolon, then ran the string through
  Invoke-Expression. PowerShell therefore treated the semicolon as its own
  statement separator (only the first wt call ever ran) and wt.exe received
  a literally quoted subcommand word, which it does not recognise -- so
  Windows Terminal opened its Help popup instead of the wall. The fix: pass
  an argument ARRAY to wt.exe with BARE subcommand names and one discrete
  separator element per split (wt's documented separator), never
  Invoke-Expression. Single-instance attach (-w 0) is preserved.
#>
param(
    [ValidateSet(1, 4, 8, 16, 32, 64)][int]$Slots = 64,
    # Optional real slot command, e.g. 'muse --yolo'. UNVERIFIED 2026-09-24:
    # the installed Muse CLI was never reachable from this session (no shell
    # runner), so MUSE_EXECUTABLE / MUSE_YOLO_SUPPORTED are UNKNOWN and this
    # MUST stay empty until verified on the machine. Empty = safe monitor
    # mode (watcher.py shows slot state; no provider is ever launched).
    [string]$SlotCommand = ''
)

$ErrorActionPreference = 'Stop'

$wallDir = $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $wallDir)
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Project virtual environment is required.' }
$watcher = Join-Path $wallDir 'watcher.py'
if (-not (Test-Path $watcher)) { throw "watcher.py not found: $watcher" }

$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if (-not $wt) { throw 'Windows Terminal (wt.exe) was not found on PATH.' }

# One wt.exe argument array. Every ";" is a single-element entry so that
# PowerShell passes it through as wt's pane/tab separator.
$wtArgs = @('-w', '0', 'new-tab', '--title', 'Courier Control', '-d', $repoRoot)
$wtArgs += @(';', 'split-pane', '--title', 'Courier Logs', '-d', $repoRoot)

$useMuse = -not [string]::IsNullOrWhiteSpace($SlotCommand)
if ($useMuse) {
    $museTokens = @($SlotCommand -split '\s+')
    if ($museTokens.Count -eq 0) { throw 'SlotCommand is blank.' }
}

$slotId = 1
$tab = 1
while ($slotId -le $Slots) {
    $title = ('MUSE-{0:D2}' -f $slotId)
    # A real Muse slot starts in its OWN canonical workdir so sessions never
    # share a cwd. Monitor mode keeps the old wall dir.
    $slotWorkdir = Join-Path $repoRoot "runtime\slots\$title\workdir"
    if ($useMuse) {
        if (-not (Test-Path $slotWorkdir)) { New-Item -ItemType Directory -Force -Path $slotWorkdir | Out-Null }
        $wtArgs += @(';', 'new-tab', '--title', $title, '-d', $slotWorkdir) + $museTokens
    } else {
        $wtArgs += @(';', 'new-tab', '--title', "Group $tab", '-d', $wallDir, $python, $watcher, $title)
    }
    $slotId++
    for ($pane = 2; $pane -le 8 -and $slotId -le $Slots; $pane++) {
        $paneTitle = ('MUSE-{0:D2}' -f $slotId)
        if ($useMuse) {
            $paneWorkdir = Join-Path $repoRoot "runtime\slots\$paneTitle\workdir"
            if (-not (Test-Path $paneWorkdir)) { New-Item -ItemType Directory -Force -Path $paneWorkdir | Out-Null }
            $wtArgs += @(';', 'split-pane', '--title', $paneTitle, '-d', $paneWorkdir) + $museTokens
        } else {
            $wtArgs += @(';', 'split-pane', '-d', $wallDir, $python, $watcher, $paneTitle)
        }
        $slotId++
    }
    $tab++
}

& $wt.Source @wtArgs
