# M199: State-Directory Ownership/Isolation

## Finding
The server stores mutable state in the `server/state` directory (e.g. `central_state.json` and the `artifacts/` tree). The Mac worker stores state in its local sandbox.
Because `server/app.py` does not explicitly set a umask (e.g. `os.umask(0o077)`) or pass restricted modes to `os.makedirs`, the state directories and JSON files inherit the default environment umask (typically creating `0o755` directories and `0o644` files).

## Local Check
- `os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)` in `server/app.py` uses the default `mode=0o777` (subject to umask).
- `open(temp_path, 'w')` for the state JSON uses default `0o666` (subject to umask).
- Secrets (like `COURIER_API_KEY`) are intentionally kept in environment variables and are **not** serialized to `central_state.json`. 
- The artifact binary blobs, however, *are* isolated via `0o600` permissions via `tempfile.mkstemp` (as verified in M196).

## Conclusion
The state-directory ownership and isolation rely on the standard operating system umask. Because no secrets are persisted in the JSON state, this lack of strict `0o700`/`0o600` isolation for the JSON files does not leak credentials. The artifact bytes remain protected. For multi-tenant physical Mac environments, configuring the deployment user's umask to `027` or `077` is sufficient for total isolation.

STATUS=PROVEN
