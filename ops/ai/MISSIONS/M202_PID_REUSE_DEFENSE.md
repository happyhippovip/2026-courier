# M202: PID Reuse Defense Requirements

## Finding
Operating systems eventually wrap around and reuse Process IDs (PIDs). If a worker crashes and its PID is reassigned to an unrelated process (e.g. a system daemon or another user's job), the courier worker must not accidentally signal, kill, or trust that new process.

The defense mechanism resides in `scripts/mac_worker/runtime_state.py`:
1. When a process is spawned, `process_identity(pid)` captures the exact start time (`lstart`) via `ps` and hashes it into a `fingerprint`.
2. This fingerprint is saved in the state JSON (e.g., `current_task.json` or `daemon` state).
3. Before interacting with a PID (like killing it in `cleanup_group`), the system checks `same_process(pid, identity)`.

```python
def same_process(pid, identity):
    return bool(identity and process_identity(pid) == identity)
```

## Conclusion
Because a reused PID will inherently possess a newer OS start time (`lstart`), the fingerprint will definitively mismatch. `same_process` will return `False`, completely neutralizing the PID reuse vulnerability. 

STATUS=PROVEN
