#Requires -Version 5.1
<#
  Cannon Ein-Klick-Start (Windows, Kunde).
  Startet den Motor im BEGRENZTEN local_fake-Modus (FINITE + Limit):
  kein echter Muse-Aufruf, kein Netzwerk, kein Provider.
  Garantie: CannonMotor.start(..., local_fake=$true) laesst nur
  LOCAL_FAKE-Tasks zu; der echte Muse-Pfad wird nur fuer
  Tasks mit executor_kind REAL_MUSE betreten (siehe scripts/cannon_motor.py).
  Aufruf: Doppelklick auf start_cannon_windows.bat ODER
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_cannon_windows.ps1
  Exit-Code: 0 = OK (Aufgaben erledigt, Zustand konsistent),
             1 = Lauf fehlgeschlagen, 2 = Start abgelehnt, 3 = kein Python.
#>
param(
  [int]$Limit = 0,
  [string]$StateDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

# --- Umgebungsvariablen (nur Defaults, bestehende Werte gewinnen) ---
if (-not $env:COURIER_STATE_DIR -or $StateDir -ne "") {
  if ($StateDir -ne "") { $env:COURIER_STATE_DIR = $StateDir }
  elseif (-not $env:COURIER_STATE_DIR) {
    $env:COURIER_STATE_DIR = Join-Path $env:USERPROFILE ".courier\cannon-motor"
  }
}
if (-not $env:COURIER_LIMIT -or $Limit -gt 0) {
  if ($Limit -gt 0) { $env:COURIER_LIMIT = "$Limit" }
  elseif (-not $env:COURIER_LIMIT) { $env:COURIER_LIMIT = "3" }
}
$env:COURIER_RUN_MODE = "local_fake"
$env:COURIER_NO_NETWORK = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:COURIER_REPO_ROOT = $RepoRoot
# Modus: FINITE (BEGRENZT) + local_fake, Limit aus COURIER_LIMIT.

Write-Host "Cannon Ein-Klick-Start"
Write-Host ("  Repo      : {0}" -f $RepoRoot)
Write-Host ("  State-Dir : {0}" -f $env:COURIER_STATE_DIR)
Write-Host ("  Modus     : FINITE (BEGRENZT), local_fake, Limit={0}" -f $env:COURIER_LIMIT)

# --- Python suchen ---
$PythonCmd = $null
$PythonArgsPrefix = @()
foreach ($candidate in @("python", "py")) {
  try {
    $found = Get-Command $candidate -ErrorAction Stop
    if ($candidate -eq "py") { $PythonArgsPrefix = @("-3") }
    $PythonCmd = $found.Source
    break
  } catch { }
}
if (-not $PythonCmd) {
  Write-Host "CANNON_START=FAILED reason=no_python (weder 'python' noch 'py' gefunden)"
  exit 3
}
Write-Host ("  Python    : {0}" -f $PythonCmd)

# --- eingebetteter Starter (stdlib only, FINITE + Limit + local_fake) ---
$StarterCode = @'
import json, os, sys
sys.path.insert(0, os.environ.get("COURIER_REPO_ROOT", "."))
from scripts.cannon_motor import CannonMotor
state_dir = os.environ.get("COURIER_STATE_DIR")
limit = int(os.environ.get("COURIER_LIMIT", "3"))
motor = CannonMotor(state_dir)
started = motor.start(mode="FINITE", limit=limit, cooldown=0.5, local_fake=True)
print("CANNON_START_REQUEST: " + json.dumps(started, default=str), flush=True)
if not started.get("started"):
    print("CANNON_START=ABORT reason=" + str(started.get("reason")), flush=True)
    sys.exit(2)
reports = motor.run(max_steps=10000)
inv = motor.invariants()
print("CANNON_RESULT state=" + motor.state
      + " started=" + str(inv["STARTED"])
      + " done=" + str(inv["DONE_COUNT"])
      + " lost=" + str(inv["LOST_RESULTS"])
      + " dup=" + str(inv["DUPLICATE_EXECUTIONS"]), flush=True)
ok = (inv["DONE_COUNT"] >= 1
      and inv["LOST_RESULTS"] == 0
      and inv["DUPLICATE_EXECUTIONS"] == 0
      and motor.state in ("COMPLETED", "IDLE"))
print("CANNON_START=" + ("OK" if ok else "FAILED"), flush=True)
sys.exit(0 if ok else 1)
'@
$TmpPy = Join-Path $env:TEMP "cannon_windows_start.py"
Set-Content -Path $TmpPy -Value $StarterCode -Encoding UTF8

& $PythonCmd @PythonArgsPrefix $TmpPy
$code = $LASTEXITCODE
Remove-Item -Path $TmpPy -ErrorAction SilentlyContinue

if ($code -eq 0) {
  Write-Host ("CANNON_START=OK state_dir={0}" -f $env:COURIER_STATE_DIR)
} else {
  Write-Host ("CANNON_START=FAILED exit={0} state_dir={1}" -f $code, $env:COURIER_STATE_DIR)
}
exit $code
