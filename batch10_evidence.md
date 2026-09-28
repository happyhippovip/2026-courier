# Batch 10 Evidence

## Substep 1: Intake Dispatcher State Path
- **Fehler**: `scripts/intake_dispatcher.py` wrote directly to `central_state.json` in the current working directory, ignoring the `COURIER_STATE_FILE` environment variable which defaults to `server/state/central_state.json`. This meant the intake dispatcher updated an isolated state file instead of the actual server state.
- **Fix**: Replaced the hardcoded `'central_state.json'` with `os.environ.get("COURIER_STATE_FILE", "server/state/central_state.json")` and ensured intermediate directories are created.
- **Check/Test**: Wrote and executed `test_intake_dispatcher_state_file.py` to ensure the intake dispatcher correctly reads the environment variable and writes to the configured state file instead of CWD. The test passes successfully.

## Substep 2 & 3: Mac Worker Heartbeat and Upload Rejection (Patch Package)
- **Fehler**: `mac_worker/daemon.py` suffers from the exact same two bugs as `windows_worker/daemon.py`:
  1. Long running tasks in `run_native` and `run_agy` (with `timeout=600` and `timeout=300` respectively) block the main loop, preventing heartbeats from being sent. This causes the server to wrongly quarantine the tasks as `WORKER_RESTARTED_AND_LOST_STATE`.
  2. If an artifact upload is permanently rejected by the server (e.g. 413 Payload Too Large), the daemon sets `worker_phase = "RELEASE_PENDING"` and drops the task. This loses the exact error message and causes an ambiguous failure.
- **Fix**: As an authorized Windows Central Writer, I cannot modify `mac_worker/daemon.py` directly. Instead, I created an exact patch package (`mac_worker_patch_package.py`) which automates the application of both fixes:
  1. Introduces a background heartbeat thread during `subprocess.Popen.communicate`.
  2. Intercepts `REJECTED` upload outcomes, converts them to a `FAILED` result with `stderr` containing the error, and submits it to the server.
- **Check/Test**: Successfully generated the patch package. All 352 unit tests continue to pass with zero regressions.
