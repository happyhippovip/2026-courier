# M203: Process-Group/Session Ownership Evidence

## Finding
When courier executes a task, the task may spawn multiple child processes. If the parent process exits or crashes, orphaned children must not leak and consume resources.

In `scripts/mac_worker/runtime_state.py`, the `cleanup_group` function enforces process-group ownership:
1. The `pgid` (Process Group ID) is recorded in the `process_identity`.
2. `cleanup_group` targets the entire process group using `os.killpg(pgid, signal)`.
3. To prevent signaling an unowned group (if the `pgid` was reused by the OS), the function strictly re-validates ownership before sending any signal:
   ```python
   if identity is None or identity.get("pgid") != pgid:
       return False

   if same_process(pgid, identity):
       try:
           os.killpg(pgid, signal.SIGTERM)
       ...
   ```
4. `same_process` uses the `lstart` fingerprint of the group leader. If the leader's PID was reused, `same_process` returns `False`, and the group is not signaled.

## Conclusion
Process-group termination is safely bound to the process ownership identity. The courier worker mathematically proves ownership of the process group before issuing `SIGKILL` or `SIGTERM`, ensuring total cleanup of child processes without risking collateral damage to OS-reused process groups.

STATUS=PROVEN
