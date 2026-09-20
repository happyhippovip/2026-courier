# WINDOWS RUNTIME PERMANENT RULES

This document serves as the immutable reference for the Courier Windows primary worker and customer execution lifecycle. The principles below dictate how the product operates on the customer's machine.

### 1. TERMINAL CLEANUP REQUIRED
All task-owned processes must close automatically on any terminal state (DONE, FAILED_TERMINAL, HUMAN_REQUIRED, CANCELLED, STALE, TIMEOUT).

### 2. NO BROAD KILL
Never use broad termination commands (e.g., `Stop-Process -Name python` or `taskkill /IM python.exe`). Terminate exactly and only the specific process tree owned by the task.

### 3. LOW-END HARDWARE SUPPORT
The default profile (`LOW_RESOURCE`) must run safely on minimal hardware. This means max one heavy local task, conservative parallelism, sleep-based idle polling, and fallback to hosted execution if the local machine is saturated.

### 4. ACCOUNT SWITCH DURABILITY
Account or provider switches must never lose queue items. A switch checkpoints active items to `WAITING_PROVIDER`, closes exact PIDs, and seamlessly resumes exactly the same item once the new credentials are provided.

### 5. QUEUE SURVIVES QUOTA
Quota exhaustion failures are NOT terminal. The system moves the task to `WAITING_PROVIDER` and gracefully spins down processing without losing task identity.

### 6. UI NOT AUTHORITY
The UI is a thin representation. Real state resides exclusively in `central_state.json`. If a UI handle is stale, it must be removed.

### 7. CHAT NOT AUTHORITY
We never rely on scrolling the chat or re-pasting old prompts to reconstruct a queued task. All queue data must be durably persisted.

### 8. CUSTOMER NO MANUAL ENV
Customers must never be required to manually set API keys in their system environment variables. Credentials must be managed securely and implicitly via the runtime configuration and keychain/lock mechanisms.

### 9. CUSTOMER NO PYTHONPATH
Customers must never have to debug Python module paths or run manual shell commands to start the Courier service. The lifecycle (install, autostart, run) is fully containerized/scheduled natively.

### 10. SAFE UPDATE/ROLLBACK
Updates must be completely non-destructive to state. Migrations are idempotent. If a post-update health check fails, the local runtime reverts state gracefully from a backup.
