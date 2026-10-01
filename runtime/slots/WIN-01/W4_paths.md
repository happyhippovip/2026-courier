# W4 RESULT — Installer/wall path+quoting audit (static, read-only)

MODE: shell-less LIGHT. Audited: 3 Scheduled-Task installers, 2 starter
.bats, wall ps1 root-derivation (9 files), .lnk installer, stop_all_slots.
No execution. Windows scope only.

## Verified sound
- Root derivation UNIFORM: $PSScriptRoot + double Split-Path (9/9 wall ps1).
  Zero hardcoded repo/user paths in wall scripts.
- .lnk args quote the launcher path (`"{0}"`, spaces-safe);
  WorkingDirectory=repoRoot; $ErrorActionPreference=Stop; COM released;
  preservation contract honored (Muse Original untouched).
- .bat self-cd quoted + drive-aware (cd /d "%~dp0\.."); start /B commands
  quoted. UV_PROJECT_ENVIRONMENT unquoted SET is space-safe (SET takes the
  full line).
- stop_all_slots = exact-process via supervisor (PID+create_time), no broad
  kills. Task settings: bounded restarts (3x1min), no execution time limit
  (correct for long-run motor).

## Findings
Q-W4-1 (INFO) INSTALLERS OMIT -WorkingDirectory.
Harmless today (.bats self-cd first thing); adding -WorkingDirectory would
be defense-in-depth for future edits that assume CWD. Owner: installers.
Q-W4-2 (INFO) FLEET IS EXACT-PROCESS EXCEPT ONE OUTLIER.
Every stop path is owned-process-scoped except uninstall.ps1:31 (broad CIM
kill, PS-W2-1). The outlier is the exception, not the rule.

## Disposition
READ ONLY. No path/quoting defects requiring repair found.
No files outside runtime/slots/WIN-01 touched.
