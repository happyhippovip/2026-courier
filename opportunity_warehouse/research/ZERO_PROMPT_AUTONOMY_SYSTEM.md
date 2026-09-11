# OPPORTUNITY WAREHOUSE RESEARCH: ZERO-PROMPT AUTONOMY SYSTEM

## Topic ID: OP-ZERO-PROMPT-001
- **Domain**: Runtime Execution & Bot Autonomy
- **Classification**: Core Platform Infrastructure / Non-Interactive Foundation
- **Target OS**: Windows 11 / Server & macOS Darwin
- **Discovered In**: Real Operator Workflow (Operator blocked by 1-hour repeated "1. Yes" prompts)
- **Status**: SOLVED, PACKAGED & PRODUCTION-ANCHORED

### Problem Analysis
Standard Antigravity CLI falls back to an interactive confirmation card for every tool call and file write if flags or configuration profiles are missing. This turns unattended agent jobs into babysitting loops.

### Solution Architecture
1. **Preconfigured Profile**: `settings.json` with `toolPermission=always-proceed`, `artifactReviewPolicy=always-proceed`, `altScreenMode=never`.
2. **Execution Flags**: `--sandbox --dangerously-skip-permissions --mode accept-edits`.
3. **Cross-Platform Automation**: Automated 1-click installers for Windows (`install_windows_autonomy.ps1`) and macOS (`install_mac_autonomy.sh`).
4. **Permanent System Anchoring**: PowerShell Profile functions and patched launcher batch/cmd files.
