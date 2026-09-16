# Mac Worker Fresh-Machine Replacement Procedure

The Courier Mac runtime is designed to treat individual worker machines as entirely stateless, ephemeral, and replaceable. The absolute truth of all workflows, tasks, and state transitions resides strictly in the canonical Courier Server (`central_state.json`), never on the worker.

When a Mac worker machine is lost, corrupted, or replaced, the following is the shortest supported path to seamlessly continue operations.

## 1. Install Product Runtime
Download or clone the target codebase release (e.g. `2026-courier`) on the new machine. Execute the deployment script:
```bash
./deploy/install_mac_runtime.sh
```
*This idempotently creates `~/.courier_runtime`, provisions the python virtual environment, and installs the LaunchDaemons.*

## 2. Obtain & Configure Secure Credentials
Using the native macOS Keychain (the authoritative secret store), configure the Courier API keys. No API keys are placed in source control, config files, or exported via `PYTHONPATH`/environment variables:
```bash
./scripts/mac_worker/setup_keychain.sh
```
*You will be prompted to paste the secret key into a secure macOS dialog. The key is never echoed to the terminal.*

## 3. Register Capability & Start
Load the worker LaunchDaemon.
```bash
launchctl load ~/Library/LaunchAgents/com.courier.mac_worker.plist
```
*The worker automatically polls `/workers/register` declaring its identity (e.g. `MAC-01`), cost class (`high`), and capabilities.*

## 4. Reconstruct Work & Continue
Because no old chat history, no old terminal contexts, and no local transient state files (`current_task.json`) are required:
- Any task previously assigned to the dead worker will be detected by the server's `reclaim_stale` routine after 5 minutes of missed heartbeats.
- The server re-queues eligible tasks or flags ambiguous effects for `HUMAN_REQUIRED`.
- The fresh Mac worker immediately begins polling `/tasks/claim` and pulling the next eligible `QUEUED` task payload natively via HTTP. 

**Result**: The new machine organically resumes canonical work exactly where the previous machine left off, entirely decoupled from the dead machine's local state.
