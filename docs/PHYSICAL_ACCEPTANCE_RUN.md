# Physical Acceptance Run: Windows & Mac

## 1. Prepare Task Set
Run `python3 scripts/acceptance/prepare_physical_run.py` to inject the official 10-task physical proof goal into `central_state.json`.

This task set includes:
- **10 real eligible tasks** with `mode: NATIVE` (no mock environments).
- Explicit interleaving between `mac` and `windows` workers.

## 2. Prepare Worker Identities
- **Worker 1 (Mac)**: Dispatched natively via `python3 scripts/mac_worker/daemon.py`. Target: `mac` capability.
- **Worker 2 (Windows)**: Dispatched securely on a physical Windows machine via `install_service.ps1` (or `start.bat`). Target: `windows` capability.

## 3. Prepare Restart Scenario (Crash Survival)
Tasks `pt-07` and `pt-08` are designed to execute code that intentionally crashes the worker daemon:
- Mac: `python3 -c "import os, signal; os.kill(os.getppid(), signal.SIGKILL)"`
- Windows: `python -c "import os, subprocess; subprocess.run(['taskkill', '/F', '/PID', str(os.getppid())])"`
**Observation**: The workers must independently restart (via `launchd` and `run_loop.bat`), detect the orphaned `effect_marker.json`, submit an `AMBIGUOUS_CRASH`, and gracefully resume fetching the next task. 

## 4. Prepare WAITING_PROVIDER Scenario (Quota Survival)
Tasks `pt-05` and `pt-06` execute `echo quota exceeded`. 
**Observation**: The daemon parses this text, intercepts the simulated 429 response, and transitions the state to `WAITING_PROVIDER` securely without treating it as a terminal crash.

## 5. Prepare Observation Points & Counters
Do NOT manufacture metrics. Extract them from real server logs and ledger state:
- `USER_CONTINUE_MESSAGES=0`: Inspect interactive terminal (should be completely unattended).
- `MANUAL_PROCESS_RESTARTS=0`: Verify daemons restart autonomously.
- `DUPLICATE_EXTERNAL_EFFECTS=0`: Confirm via server API `409 CONFLICT` logs.
- **Pipeline Proof**: Trace `server.log` to confirm the lifecycle `DISPATCHED` -> result -> verification -> reconciliation -> `READY`.
- `DONE -> CLEAN_IDLE`: Monitor `/goals` endpoint to verify terminal IDLE resting state.

## Execution
Once deployed, monitor the pipeline via `cat server/state/central_state.json`.
