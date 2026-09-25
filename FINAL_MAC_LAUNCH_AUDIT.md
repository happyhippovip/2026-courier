# FINAL MAC LAUNCH AUDIT

## Investigation of Mac Launchers & Background Processes

### 1. Launchd Service Boundary
The Mac host deploys automated daemons managed by `launchctl`. The installation is handled by `deploy/install_mac_runtime.sh`, creating `.plist` agents in `~/Library/LaunchAgents`. 
There are exactly four persistent launchd services:
- `com.courier.server`: Starts `python3 -m server.app` from `$PROJECT_ROOT` to run the orchestrator and central state manager.
- `com.courier.verifier`: Starts `courier_verifier.py` from `$RUNTIME_DIR`.
- `com.courier.motor`: Starts `courier_continue.py --run` from `$PROJECT_ROOT`.
- `com.courier.mac_worker`: Starts `scripts/mac_worker/daemon.py` from `$RUNTIME_DIR`.

These services ensure that if Courier crashes, it resumes executing physical goals continuously without human interaction.

### 2. Terminal-Wall Launcher
- **Path**: `scripts/mac_worker/Terminal-Wall-BACKGROUND.py`
- **Purpose**: Massively parallel background screen orchestrator. It manages concurrent execution slots using an Adaptive Capacity Governor.
- **Execution Mechanism**: It dynamically spawns background instances of either `muse --yolo` or `HOME=/Users/user/.gemini_alt agy` utilizing detached GNU `screen` sessions (`screen -dmS <slot_id> bash -c <cmd>`).
- **State tracking**: Tracks slots in a CSV state file and creates file-system level leases in a `.courier_claims` directory. 
- **Notes**: This script interfaces with a queue script (via CLI execution rather than HTTP) to claim tasks and submit completions, acting as a heavier alternative to the standard Python-native `daemon.py`.

## Next Steps
This concludes the `COURIER MAC — LAUNCHER / PROCESS AUDIT` task.
We now proceed to the final safety task: **COURIER TERMINAL WALL — INDEPENDENT REVIEWER** (Read-only review of `Terminal-Wall-Control.command`, which is being edited by Opus).
