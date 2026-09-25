# P0 MUTATION TRACE

## Forensic Analysis: Checkout / Ledger / Runtime Modifiers on macOS

### 1. Checkout (Git/Source Truth)
- **Primary Modifier**: `git` operations (pull, clone, checkout, rebase).
- **Secondary Modifiers**: Direct source file edits via code editors or AI tooling (Antigravity).
- **Detection**: `scripts/runtime_truth.py` verifies the checkout integrity by extracting `CANONICAL_HEAD_SHA` (using `git rev-parse HEAD`), `DEPLOYED_SHA` (via `~/.courier_runtime/.git` or `.deployed_sha`), and the `REMOTE_HEAD_SHA`.

### 2. Ledger (agent_handoff_ledger.json)
- **Primary Modifiers**: 
  - `scripts/courier_continue.py`: Orchestrates transitions, performs checkpoint updates, and commits ledger modifications.
  - `scripts/agent_handoff_ledger.py`: The underlying library module providing `update()`, `acquire_lease()`, and `verify_fencing_token()` to serialize structural ledger writes.
  - `scripts/feed_evidence.py`: Appends physical execution evidence bounds directly to the ledger guard payload.
- **Detection**: The ledger stores a rigid schema with an optimistic concurrency `fencing_token`. `scripts/runtime_truth.py` cross-references `TESTED_SHA` and `ACCEPTANCE_BOUND_SHA` against the physical checkout bounds.

### 3. Runtime (Server State & Motor Processes)
- **Central State Modifier**: `server/app.py` directly writes to `state/central_state.json` using `@serialize_state_mutation` (RLock). It coordinates worker registration, task dispatching, verification, and goal fulfillment.
- **Motor / Worker Modifiers**: `scripts/mac_worker/daemon.py` mutates local worker task tracking state (`current_task.json` and `current_result.json`) and triggers physical task capabilities via external subprocess execution on the host macOS system.
- **Detection**: `scripts/runtime_truth.py` inspects the live host using `ps -eo pid,command` and `lsof` to trace the running `mac_worker/daemon.py` processes, verify their execution `cwd` bounds, and evaluate the product health check script (`RUNTIME_HEALTH`).

## Next Steps
This concludes the `P0 MUTATION TRACE / FORENSIK` read-only verification. We now proceed to the next immediate safety task: **COURIER — DOCUMENTATION REALITY CHECK**.
