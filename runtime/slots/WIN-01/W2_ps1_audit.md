# W2 RESULT — PS1 quoting/kill-surface audit (static, read-only)

MODE: shell-less LIGHT. Audited 15 ps1 files (wall 9 + worker 3 + motor/
verifier installers). No execution. Windows scope only.

## Verified sound (at HEAD)
- Invoke-Expression: ZERO live uses (only fix-history comments in
  muse_wall_launcher.ps1:8-14). The 2026-09-24 anti-pattern is gone.
- Launcher array form VERIFIED: $wtArgs with bare new-tab/split-pane,
  ';' as separate elements, -w 0 (launcher:40-64).
- SilentlyContinue elsewhere = correct probe pattern (Get-Command /
  Get-Process / Get-ScheduledTask existence checks) or job cleanup.
- Non-ASCII = em-dashes in comments only (BOM files — keep BOM).

## Findings (for owners — read-only, no WRITE_SCOPE)
PS-W2-1 (MEDIUM) UNINSTALL USES BROAD COMMANDLINE KILL.
uninstall.ps1:31: Get-CimInstance Win32_Process | Where CommandLine
-match "daemon.py|start.bat" | Terminate. Matches ANY process with those
substrings — including mac_worker/daemon.py (same filename) and foreign
start.bat users. Violates exact-process ownership + PROCESS_SAFETY
(unknown ownership must block destructive cleanup). THE SAFE ALTERNATIVE
ALREADY EXISTS IN-REPO: stop_safe.py (lock-file PID + create_time verify
+ exact tree terminate + stale-lock cleanup). Fix direction: uninstall
step [4] should invoke stop_safe.py instead of CIM matching. Reuse, not
rebuild. Owner: windows worker/installer scope.

PS-W2-2 (LOW) UNINSTALL SELF-DELETES ITS OWN DIRECTORY.
uninstall.ps1:35 Remove-Item $PSScriptRoot -Recurse -Force (opt-in
-RemoveData) runs from inside the deleted tree; SilentlyContinue hides
partial failure. Explicit flag, but self-destruct + silent = risky combo.

PS-W2-3 (INFO) TASK-START ERROR SWALLOWED 30s.
bootstrap.ps1:113 Start-ScheduledTask SilentlyContinue; failure only
surfaces via the later 30s log-watch gate. Fail-closed holds (T8); an
immediate warning would shorten diagnosis.

## Disposition
READ ONLY. PS-W2-1..3 to worker/installer owners.
No files outside runtime/slots/WIN-01 touched. No Mac scope touched.
