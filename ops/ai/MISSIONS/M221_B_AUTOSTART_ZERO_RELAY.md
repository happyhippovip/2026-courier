# M221: B Autostart Zero Relay

## Goal
Prove that the native worker can autostart and continuously pull tasks without any human relay or manual triggering logic.

## Implementation & Proof
1. **Autonomous Daemon Loop**:
   - `scripts/windows_worker/daemon.py` implements a continuously executing `while True:` loop.
2. **Self-Registration**:
   - On encountering a `404 Not Found` for its heartbeat, the worker daemon automatically calls `/workers/register` to dynamically insert itself into the active topology.
3. **Autonomous Task Polling**:
   - When resource pressure is safe (checked via WMI/WQL queries on Windows), the daemon autonomously executes a `POST` to `/tasks/claim`. It immediately begins execution upon receiving an assignment.
4. **Zero Human Gate**:
   - The entire process requires exactly zero manual triggers, relay hooks, or watchdog scripts. The daemon independently orchestrates its lifecycle.

## Conclusion
Courier achieves true zero-relay autonomy for execution pools through its self-healing, self-registering worker daemons.
