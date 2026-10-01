# M205: Stale Listener Detection Plan

## Goal
Establish a reliable mechanism to detect and reject execution environments where a lingering, unaccounted-for server process (stale listener) remains active, preventing accidental cross-run state pollution.

## Mechanism

### 1. Preflight TCP Port Validation
Before any new execution components are started, the execution scripts (`run_1_mac.sh` and `run_2_mac.sh`) explicitly check for any processes listening on the target port (8080).
```bash
if lsof -i :8080 | grep -q "LISTEN"; then
    echo "ERROR: Port 8080 is already in use. Run aborted."
    exit 1
fi
```
This serves as the primary barrier. If any stale `server.app` or unrelated service is bound to `8080`, the script forcefully halts execution. 

### 2. Immediate Server-Side Failure on Bind Collision
Currently, `server/app.py` uses the standard Flask/Werkzeug development server:
```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
```
If the preflight check is somehow bypassed or a race condition occurs where another process binds `8080` right after `lsof` succeeds but before Python executes, the `app.run` call will raise a socket error (e.g., `OSError: [Errno 98] Address already in use` on Linux, `[Errno 48]` on macOS). 

The application does **not** employ dynamic port negotiation (it never randomly picks an open port like `8081`). This guarantees failure rather than silent corruption.

### 3. Detection Plan for Enhancements
While the current approach provides strong barriers, a comprehensive detection plan involves:
1. **Graceful Fail-Fast**: `app.py` parsing `--port` (currently it ignores the `--port=8080` CLI argument and hardcodes `8080`).
2. **Explicit Readiness Ping**: The worker scripts should ping `http://127.0.0.1:8080/health` (or equivalent) to ensure the server that answers has the correct run fingerprint (e.g., matching a generated UUID passed at startup). This prevents the worker from accidentally talking to a stale server that survived the `lsof` check (e.g., if it was bound to `127.0.0.1` but `lsof` didn't catch it correctly due to arguments, though `lsof -i :8080` is fairly robust).

## Conclusion
The stale listener detection plan rests on a strict port-binding requirement. By rejecting dynamic ports and relying on OS-level TCP exclusive binding rules, physical execution boundaries are enforced. Any stale listener automatically triggers a fatal failure, ensuring no test executes against dirty state.
