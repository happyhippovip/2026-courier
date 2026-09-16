# COURIER PRODUCTION ROLLBACK PLAN

## 1. Instant Rollback Conditions
Rollback is triggered immediately if:
- Any test in the 64-test suite fails or times out.
- Any process termination attempts to kill an unverified PID.
- Any filesystem lock collision or case anomaly is detected.
- Any unexpected file modification occurs outside `courier/supervisor/`.

## 2. Instant Rollback Procedure
Execute the following single PowerShell command to revert production to its exact prior state:

```powershell
# Restore from git and remove added directories
cd C:\Users\lol\2026-workspace\courier
git checkout HEAD -- supervisor/no_stacking.js supervisor/lease_manager.js supervisor/decision_engine.js supervisor/progress_tracker.js supervisor/index.js
if (Test-Path supervisor/governance) { Remove-Item -Recurse -Force supervisor/governance }
if (Test-Path supervisor/core) { Remove-Item -Recurse -Force supervisor/core }
& "C:\Users\lol\AppData\Local\OpenAI\Codex\runtimes\cua_node\b58ca2eaa616c2da\bin\node.exe" tests/test_supervisor_plane_p0.js
```

## 3. Data Safety Invariant
The rollback leaves existing audit ledgers and event logs intact. No checkpoints or transaction histories are deleted during rollback.
