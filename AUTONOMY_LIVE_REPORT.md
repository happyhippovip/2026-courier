# COURIER V1 AUTONOMY LIVE REPORT

## Architecture Summary
The Courier autonomous worker architecture operates via a multi-step coordination protocol between the Mac Host and the Windows Native Host over an SMB share.

## Worker Paths
1. **Windows Worker Path**: Dispatched via `mac_windows_dispatcher.py` to `coordination/mac_to_windows/requests/`. Executed natively on Windows, with the output returned to `coordination/windows_to_mac/results/`.
2. **Mac CLI1 Worker Path**: Executed locally on the Mac via `courier_real_worker_adapters.py`, writing directly to the `windows_to_mac/results/` coordination queue for native consumption.
3. **Codex Worker Path**: Dispatched via `run_codex_bridge.py` and handled by the isolated Codex environment.

## Causal Evidence Chain
- **Goal Injection**: `Goal for Step 8 v20`
- **Planner Dispatch (Task A - Windows)**: `plan-win-9ddeccc7`
- **Result A (Windows)**: `REQ-MAC-9b3443cc` -> Consumed natively, generating ACK.
- **Planner Continuation**: Planner evaluated the historical payload and derived **Task B**.
- **Planner Dispatch (Task B - Mac)**: `plan-mac-0b288070`
- **Result B (Mac)**: `REQ-MAC-7a1f2585` -> Consumed natively, verified, generating ACK.
- **Goal Satisfied**: The autonomous workflow recognized both steps as successful and reached `GOAL_SATISFIED`.

This report was produced entirely through the autonomous Courier workflow.
