# Courier Canonical Bootstrap

To start or resume Courier execution autonomously as a fresh worker without requiring previous chat history or context pasting:

1. Run the canonical unattended continuation entrypoint:
   ```bash
   python3 scripts/courier_continue.py --run
   ```

## Architecture Invariants

* **Motor** = Sole runtime scheduler and authority.
* **Ledger** = Durable coordination, evidence, and zero-chat handoff mechanism. Never a second scheduler.
* **Execution Plan** = `COURIER_AUTONOMOUS_EXECUTION_PLAN.md` defines the ordered milestones.
* **Canonical Ledger Location**: `agent_handoff_ledger.json`

## Durable Restart & Machine Reboot

Courier uses native OS-service process ownership (Motor infrastructure) to guarantee deterministic recovery:

* **Machine Reboots & Worker Crashes**: The Motor runtime should be installed via its OS-specific daemon script (e.g. `scripts/start_daemon.sh` or systemd/launchd equivalents for macOS). Motor persists task state automatically. 
* **Terminal Closes & Session Ends**: Google Antigravity/CLI sessions are strictly **disposable workers**. If the session ends, the worker yields cleanly.
* **Session Replacement**: On a fresh session, simply run `python3 scripts/courier_continue.py --run`. It reconstructs the exact active frontier strictly from Git and the machine-readable Ledger without any chat history.

## Night Mode Safety

Unattended execution (`--run`) obeys strict boundaries.
* Safe/free/reversible actions execute continuously.
* Destructive actions, spending, unattended PR merges, or unverified external communications are blocked via scope-local Ledger gates.
* When a dependent scope is blocked by a gate, the worker seamlessly pivots to independent safe work (e.g., pilot collateral).
