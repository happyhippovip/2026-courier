# M201: Process Ownership Identity Fields

## Finding
When courier manages worker processes on macOS, it must identify processes uniquely to avoid signaling a new, unrelated process if a PID is reused by the operating system after the original process dies.

In `scripts/mac_worker/runtime_state.py`, the `process_identity` function gathers fields to uniquely fingerprint a process:
```python
def process_identity(pid):
    """No command arguments/secrets persisted; include OS start time, PGID, executable."""
    try:
        value = subprocess.check_output(
            ["ps", "-p", str(int(pid)), "-o", "pid=,pgid=,lstart=,comm="],
            text=True, timeout=2, stderr=subprocess.DEVNULL).strip()
        parts = value.split()
        if len(parts) < 8 or int(parts[0]) != int(pid):
            return None
        return {"pid": int(pid), "pgid": int(parts[1]),
                "fingerprint": hashlib.sha256(" ".join(parts[:7]).encode()).hexdigest()}
    except ...
```

This identity consists of:
1. `pid`: The numerical Process ID.
2. `pgid`: The Process Group ID (for identifying sibling/child processes).
3. `fingerprint`: A SHA256 hash of the `ps` output up to the 7th field, which inherently includes `lstart` (the exact start time string of the process). 

Crucially, **no command arguments** or secrets are captured. The `comm` field only shows the executable name (e.g. `python3`), not the arguments. This guarantees that API keys or task-specific secret strings passed via the command line or environment are never written to the disk in `current_task.json` state files.

## Conclusion
The identity fingerprint captures `lstart` (start time) via `ps`, preventing PID reuse collisions. It avoids persisting command-line arguments to prevent credential leakage.

STATUS=PROVEN
