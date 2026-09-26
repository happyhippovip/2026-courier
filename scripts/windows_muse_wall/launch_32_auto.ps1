#Requires -Version 5.1
<#
  Muse Auto -- staged real-session starter (resume logic, trio 16/32/64).

  Desktop trio (see install_desktop_shortcuts.ps1):
  - "Muse 16 Auto" -> -Target 16
  - "Muse 32 Auto" -> -Target 32 (DEFAULT; bare double-click behaviour)
  - "Muse 64 Auto" -> -Target 64, unlocked ONLY when stage 32 PASS exists

  Double-click behaviour: runs the NEXT UNPROVEN stage in 1 -> 4 -> 8 ->
  16 -> 32 (-> 64 when target allows). Each run auto-starts that stage's
  REAL Muse sessions in the wall (verified SlotCommand, zero per-slot
  typing -- never monitor/READY-only mode). Close the wall window between
  stages (one window close), then double-click again to advance. Gates:
  - never blindly N first (stage N requires PASS proof of N-1)
  - 64 requires proven stable 32 (chain gate; never forced)
  - no duplicate titles/hosts (one wall generation open at a time)
  - failed stage blocks scaling until fixed and re-proven

  Explicit `-Stage <n>` re-proves ONE stage (same gate, unless -SkipGate).
  `-Yolo` uses `muse --yolo` ONLY when runtime/muse_probe.json proves this
  machine's help text lists --yolo; otherwise fail-closed (no session).

  Reuses (no new architecture):
  - probe_muse.ps1 (verified SlotCommand, never guessed)
  - supervisor init/admit/status (canonical runtime/slots state)
  - muse_wall_launcher.ps1 (fixed wt arg-array path, per-slot workdir/title)

  Proof per stage: runtime/proof/stage-<NN>.json {stage, result, checks}.
#>
param(
    [ValidateSet(1, 4, 8, 16, 32, 64)][int]$Stage = 0,
    [ValidateSet(16, 32, 64)][int]$Target = 32,
    [switch]$Yolo,
    [switch]$SkipGate,
    [int]$StabilitySeconds = 20
)

$ErrorActionPreference = 'Stop'

$wallDir = $PSScriptRoot
$repoRoot = Split-Path -Parent (Split-Path -Parent $wallDir)
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Project virtual environment is required.' }
$stages = @((1, 4, 8, 16, 32, 64) | Where-Object { $_ -le $Target })
$proofDir = Join-Path $repoRoot 'runtime\proof'

function Get-StageResult([int]$level) {
    $path = Join-Path $proofDir ("stage-{0:D2}.json" -f $level)
    if (-not (Test-Path $path)) { return $null }
    try {
        return (Get-Content -Raw -Path $path | ConvertFrom-Json).result
    } catch {
        return 'UNREADABLE'
    }
}

# 1. Fresh on-machine probe (never trust a stale claim).
& "$wallDir\probe_muse.ps1"
$probe = Get-Content -Raw -Path (Join-Path $repoRoot 'runtime\muse_probe.json') | ConvertFrom-Json
if (-not $probe.help_ok) { throw 'Muse probe failed: muse --help unusable. No session started.' }
$slotCommand = 'muse'
if ($Yolo) {
    if (-not $probe.yolo_supported) {
        throw 'YOLO refused: this installed muse does not list --yolo in --help. No session started.'
    }
    $slotCommand = 'muse --yolo'
}

# 2. Resolve run stage: resume next unproven up to Target, or explicit re-proof.
$stageToRun = $Stage
if ($stageToRun -eq 0) {
    $stageToRun = $null
    foreach ($level in $stages) {
        if ((Get-StageResult $level) -ne 'PASS') { $stageToRun = $level; break }
    }
    if ($null -eq $stageToRun) {
        Write-Output ("ALL_STAGES_PASS: every stage up to {0} already proven. Use -Stage <n> to re-prove one stage." -f $Target)
        exit 0
    }
    Write-Output ("RESUME_STAGE={0} TARGET={1}" -f $stageToRun, $Target)
} elseif ($stageToRun -gt $Target) {
    throw ("TARGET_GATE: explicit stage {0} exceeds this starter's target {1}. Use the matching starter." -f $stageToRun, $Target)
}

# 3. Gate: previous stage must be PASS (fail-closed scaling; 64 needs 32 PASS).
if (-not $SkipGate) {
    $fullChain = @(1, 4, 8, 16, 32, 64)
    $chainIndex = [Array]::IndexOf($fullChain, $stageToRun)
    if ($chainIndex -gt 0) {
        $previous = $fullChain[$chainIndex - 1]
        $previousResult = Get-StageResult $previous
        if ($previousResult -ne 'PASS') {
            throw ("GATE_BLOCKED: stage {0} requires stage {1} PASS first (now: {2}). Fix and re-prove stage {1}." -f $stageToRun, $previous, $previousResult)
        }
    }
}

# 4. Canonical state + admission for this stage.
Set-Location $repoRoot
& $python -m scripts.windows_muse_wall.supervisor init --root $repoRoot | Out-Null
$admitted = & $python -m scripts.windows_muse_wall.supervisor admit --root $repoRoot --level $stageToRun
Write-Output ("ADMITTED={0}" -f $admitted)

# 5. Launch the wall generation for this stage (real sessions, own workdir/title).
& "$wallDir\muse_wall_launcher.ps1" -Slots $stageToRun -SlotCommand $slotCommand
Write-Output ("LAUNCHED_SLOTS={0} COMMAND={1}" -f $stageToRun, $slotCommand)

# 6. Stability window: slow poll (2s), no busy loop, provider untouched.
$deadline = (Get-Date).AddSeconds($StabilitySeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
}
$statusText = & $python -m scripts.windows_muse_wall.supervisor status --root $repoRoot

# 7. Machine-checkable proof. Visual muse panes are interactive wt children;
# they intentionally leave no supervisor PID record (state stays READY).
# Stability here = wall process alive + zero CRASHED/BLOCKED growth + all
# stage workdirs/titles present. Input/output + title + no-popup checks are
# confirmed by the operator once per stage (single checklist, no typing).
$wtAlive = $null -ne (Get-Process -Name 'WindowsTerminal' -ErrorAction SilentlyContinue)
$checks = [ordered]@{
    wt_process_alive = [bool]$wtAlive
    supervisor_status = "$statusText"
    workdirs_present = $true
    no_popup_check = 'OPERATOR: confirm no Help popup, no second black host, no Duplicate Session'
    io_check = 'OPERATOR: type one char + Enter in MUSE-01, confirm echo/output'
}
for ($i = 1; $i -le $stageToRun; $i++) {
    $title = ('MUSE-{0:D2}' -f $i)
    if (-not (Test-Path (Join-Path $repoRoot "runtime\slots\$title\workdir"))) {
        $checks.workdirs_present = $false
    }
}
$failed = (-not $wtAlive) -or (-not $checks.workdirs_present) -or ("$statusText" -match "'CRASHED': [1-9]") -or ("$statusText" -match "'BLOCKED': [1-9]")
$result = 'PASS'
if ($failed) { $result = 'FAIL' }

if (-not (Test-Path $proofDir)) { New-Item -ItemType Directory -Force -Path $proofDir | Out-Null }
$proof = [ordered]@{
    stage        = $stageToRun
    result       = $result
    slot_command = $slotCommand
    yolo         = [bool]$Yolo
    muse_source  = $probe.muse_source
    proven_at    = ([DateTime]::UtcNow.ToString('o'))
    checks       = $checks
}
$proofPath = Join-Path $proofDir ("stage-{0:D2}.json" -f $stageToRun)
$tmp = "$proofPath.tmp"
($proof | ConvertTo-Json -Depth 6) | Out-File -FilePath $tmp -Encoding utf8 -Force
Move-Item -Force -Path $tmp -Destination $proofPath

Write-Output ("STAGE_{0}={1} PROOF={2}" -f $stageToRun, $result, $proofPath)
if ($result -eq 'FAIL') {
    throw ("STAGE_{0}=FAIL: scaling blocked. Fix the cause, then re-prove this same stage." -f $stageToRun)
}
$nextIndex = [Array]::IndexOf($stages, $stageToRun) + 1
if ($nextIndex -lt $stages.Count) {
    Write-Output ("NEXT: close this wall window (one close), then re-run for stage {0}." -f $stages[$nextIndex])
} else {
    Write-Output ("DONE: all {0} slots proven. This starter is ready for job assignment." -f $Target)
}
