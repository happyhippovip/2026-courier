# KNOWN_GOOD_CHECKPOINT

## Checkpoint Status
- CHECKPOINT SAVED: YES
- WINDOWS CONFIG SAVED: YES
- MAC CONFIG SAVED: YES
- COURIER CONFIG SAVED: YES
- MUSE CONFIG SAVED: YES
- SAFE AFTER RESTART: YES

## Canonical Proven-Good State
This checkpoint records the known-good working setup for Courier across Windows and Mac environments, including event-driven orchestration, test/validate strategies, and recovery behavior.

### 1. Git State
- Tested against the `2ee8d9057347e813ffa3f31f3d0fc6f6b3396109` tree (plus local fixes for `app.py` provider lock isolation and `ChiefCommander` mode preservation).

### 2. Courier Configuration
- **Server**: Flask-based `server/app.py` acting as the central truth store. Runs on `:8080`.
- **Verifier**: `scripts/courier_verifier.py` polling `GET /tasks/pending_verification` every 5-10 seconds to validate artifacts, enforce DLQ rules (freshness, double-update prevention), and advance tasks.
- **Ledger Strictness**: Strict monotonic artifact history enforcement is enabled (DLQ-01, DLQ-02).
- **Execution Strategy**: `CONTINUOUS_FIXED_POINT` with autonomous continuation until `CLEAN_IDLE` or `HUMAN_REQUIRED`.

### 3. Windows Service / Configuration
- **Supervisor**: Runs continuously as a Windows Service/scheduled task or detached background loop.
- **Provider**: Registers as `win32_native` and polling for `target_agent: "win32"`.
- **Race conditions**: Safely protected by `Task Scheduler` wrappers or single-threaded Python event loops.

### 4. Mac Worker Configuration
- **Daemon**: `scripts/mac_worker/daemon.py` managed by macOS `launchd` (`~/Library/LaunchAgents/com.courier.mac.worker.plist`).
- **Provider**: Registers as `mac_native` (and defaults to `mac_antigravity` via `agy` for complex LLM tasks).
- **State Dir**: `scripts/mac_worker/state/` safely captures `current_task.json` and `current_result.json` for resilient restarts.

### 5. Google / Antigravity Behavior
- Uses `agy` for complex LLM-bound tasks (e.g. `mode: "ANTIGRAVITY"`).
- Background execution: All `run_command` tool calls use `IsDaemon: false` but are sent to background (Async).
- Event-driven: Antigravity does not poll; it reacts to messages or completions.
- Tools: Uses `grep_search` and `find_by_name` for minimal footprint file checks.

### 6. Muse Code Setup
- Safe directory: `/Users/user/Downloads/2026-courier/`.
- `BypassSandbox: true` applied globally for unattended operations.

### 7. Interpreter / venv / uv Setup
- Runs via system/uv python, respecting local virtual environment.
- Dependencies: Standard `requests`, `pytest`, `flask`.

### 8. Event-Driven vs Cron Behavior
- **Workers**: Continuous polling with short sleep. `WAITING_PROVIDER` tasks immediately yield the polling thread to execute non-rate-limited ready work.
- **Agents**: Wait for push notifications (Async completions) rather than cron polling.

### 9. Foreground / Background Rules
- **Foreground**: Fast edits, state modifications.
- **Background**: Tests, daemon polling, long-running validation. Background tasks must dump output to logs.

### 10. Fast / Deep Test Strategy
- **Fast Lane**: Targeted `pytest tests/test_name.py` for local file changes.
- **Deep Validations**: Torture tests `test_tomato_two_torture.py` must run to completion independently.

### 11. Secret Storage / Redaction
- Secrets (`API_KEY`, `VERIFIER_KEY`) are stripped before worker logs write to stdout/stderr.

### 12. Recovery & Power-Loss Behavior
- Workers dump `current_task.json` (on claim), `current_result.json` (on execute), and `current_provider_wait.json` (on rate limit).
- Upon restart, worker re-reads these JSON checkpoints and reconciles with central server before claiming new work. Stale claims are rejected (404/409) and silently cleared.

### 13. HUMAN_REQUIRED Rules
- Tasks flagged `HUMAN_REQUIRED` block ONLY their specific workflow branch.
- Mac worker skips the blocked branch and claims independent tasks from other active goals.
- Bounded wait (Wait for user action).

### 14. Known-Good Startup Commands
```bash
# Server & Verifier
python3 -m server.app
python3 scripts/courier_verifier.py

# Launchd Mac Worker restart
launchctl unload ~/Library/LaunchAgents/com.courier.mac.worker.plist
launchctl load ~/Library/LaunchAgents/com.courier.mac.worker.plist
```

### 15. Settings Surviving Restart
- `central_state.json` tracks goal execution.
- Ledger histories track artifact mutations.
- `mac_worker/state/*.json` ensures the worker doesn't lose completed results if the server crashes.

---
**Prepared By**: Antigravity / Codex
**Status**: ACTIVE
