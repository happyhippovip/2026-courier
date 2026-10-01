# M191: Atomic Rename Assumptions on Target Filesystem

## Finding
On macOS (the target filesystem for the pilot), `os.replace` uses the POSIX `rename(2)` system call, which is guaranteed to be atomic for files residing on the same filesystem (APFS/HFS+). The server (`server/app.py` `save_state`) uses `os.replace` for `state.json`.

## Local Check
In `server/app.py`:
```python
def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    temp_path = f"{STATE_FILE}.tmp"
    with open(temp_path, 'w') as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp_path, STATE_FILE)
```
This correctly flushes and `fsync`s the temporary file before calling `os.replace`, ensuring that a crash immediately after the atomic rename does not leave a corrupt file due to delayed disk flushing.

## Conclusion
The atomic rename assumption holds for macOS target filesystem execution. `save_state` uses safe rename and fsync.

STATUS=PROVEN
