# M195: Stale File/Cache Precedence

## Finding
When loading state, a system might be confronted with an old durable file and a stale temporary file (e.g., from a crashed write attempt). The precedence logic defines which one is trusted.

In `server/app.py`, state persistence uses atomic rename (`os.replace`). If the server crashes mid-write:
- A stale `server/state/central_state.json.tmp` file is left on disk.
- The `load_state()` function exclusively reads `server/state/central_state.json`.

```python
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            # ... returns state
    return {"goals": {}, "tasks": {}, "workers": {}}
```

## Local Check
- The `load_state` method does not contain any recovery logic attempting to load or merge `.tmp` files.
- The stale `.tmp` file is completely ignored on startup.
- The true, atomic `STATE_FILE` takes absolute precedence. 
- The stale `.tmp` file is then truncated and overwritten upon the very first state mutation (which calls `save_state` and executes `open(temp_path, 'w')`).
- There is no in-memory cache mismatch risk for the server itself, because all routes are wrapped in `@with_state_lock`, making reads and writes synchronous to the file on disk.

## Conclusion
The exact durable file (`STATE_FILE`) holds absolute precedence over any stale or temporary files, avoiding corruption from partial writes. There is no cache invalidation risk on the server because state is locked per request.

STATUS=PROVEN
