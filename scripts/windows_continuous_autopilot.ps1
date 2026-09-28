$ErrorActionPreference = "Continue"
$Repo = "C:\Users\lol\2026-workspace\2026-courier"
$PromptPath = Join-Path $env:TEMP "courier-WINDOWS_SELFTEST_CONTINUOUS_AUTOPILOT_PROMPT.txt"
$MaxHours = if ($env:MAX_HOURS) { [int]$env:MAX_HOURS } else { 8 }
$SleepSeconds = if ($env:SLEEP_SECONDS) { [int]$env:SLEEP_SECONDS } else { 45 }
$LogDir = Join-Path $Repo "logs\windows-autopilot"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Set-Location $Repo
git fetch origin coordination/autofill-task-seed-20260926
if ($LASTEXITCODE -ne 0) { Write-Host "[launcher] initial fetch failed; continuing from local durable state" }

$remote = git show "origin/coordination/autofill-task-seed-20260926:ops/ai/WINDOWS_SELFTEST_CONTINUOUS_AUTOPILOT_PROMPT.txt"
if ($LASTEXITCODE -ne 0) { throw "Cannot load autopilot prompt" }
Set-Content -Path $PromptPath -Value $remote -Encoding UTF8

if (-not (Get-Command agy -ErrorAction SilentlyContinue)) { throw "agy not found in PATH" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found in PATH" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "python not found in PATH" }

$Deadline = (Get-Date).AddHours($MaxHours)
$Run = 0
while ((Get-Date) -lt $Deadline) {
  $Run++
  $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $Log = Join-Path $LogDir "$Stamp-run$Run.log"
  Write-Host "[launcher] run=$Run log=$Log"
  $Prompt = Get-Content -Raw -Path $PromptPath
  & agy -p $Prompt --disable-slash-commands *> $Log
  $Rc = $LASTEXITCODE
  $Text = Get-Content -Raw -Path $Log -ErrorAction SilentlyContinue
  if ($Text -match "(?i)quota|rate.?limit|billing|authentication|unauthorized|forbidden|2fa|captcha") {
    Write-Host "[launcher] provider/auth gate detected; stopping repeated probes. See $Log"
    exit 20
  }
  Write-Host "[launcher] worker returned rc=$Rc; restarting in $SleepSeconds sec"
  Start-Sleep -Seconds $SleepSeconds
  git fetch origin coordination/autofill-task-seed-20260926 | Out-Null
}
Write-Host "[launcher] MAX_HOURS reached"