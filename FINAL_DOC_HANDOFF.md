# FINAL DOC HANDOFF

## Source-of-Truth Conflicts & Documentation Reality Check

I performed a comprehensive audit comparing the repository's documentation against the physical codebase. There are several massive discrepancies where the documentation describes architectures or systems that either no longer exist or were never implemented.

### 1. The `INTERNAL_ARCHITECTURE.md` Hallucination
- **Conflict**: `docs/INTERNAL_ARCHITECTURE.md` describes a system composed of `scripts/canonical_authority.py`, `scripts/host_survival_engine.py`, `scripts/live_worker_registry.py`, `scripts/snitch_observer.py`, and `scripts/continuous_safe_work_dispatcher.py` governing "OS-level flock, epoch lease" and "PID truth". 
- **Reality**: NONE of these scripts exist. The actual Courier architecture is centralized in `server/app.py` (a Flask server using `state/central_state.json` with a simple `threading.RLock()` for mutation serialization). Live worker tracking uses standard HTTP polling and UUIDs, not OS-level PIDs and flock. `docs/INTERNAL_ARCHITECTURE.md` is completely disconnected from physical reality and should be deprecated or entirely rewritten.

### 2. The `AGENT_HANDOFF_LEDGER` Role Paradox
- **Conflict**: 
  - `README.md` defines `agent_handoff_ledger.json` as the "Cryptographically hashed, Git-tracked asynchronous queue."
  - `docs/AGENT_HANDOFF_LEDGER.md` explicitly states: "It is **not** Courier runtime truth and has no scheduling, execution, dispatch, verification, queue, Motor, or daemon authority."
- **Reality**: The queue is managed centrally by `server/app.py` inside `state/central_state.json`. The `agent_handoff_ledger.json` (managed by `scripts/courier_continue.py`) functions purely as a versioned, hashed snapshot bounds-checker for agent handover, *not* as an asynchronous task queue. The `README.md` description is misleading.

### 3. Execution Masterplan vs Reality
- **Alignment**: The `docs/plans/COURIER_EXECUTION_MASTERPLAN_2026-09-24.md` correctly aligns with the state of the codebase. It acknowledges the completion of P0-P2 (Handoff Ledger integrity and Canonical authority) and correctly identifies the current physical capability (`server/app.py` supporting `mac` and `windows` capability routing for Phase P3).
- **Reality**: The execution constraints laid out in the OPUS Masterplan (like `PERSISTENCE_PENDING` and capability-based boundaries) are actively implemented in the real codebase (`server/app.py`'s `_worker_is_eligible`).

## Next Steps
This concludes the `COURIER — DOCUMENTATION REALITY CHECK` task.
We now proceed to the next immediate safety task: **COURIER MAC — LAUNCHER / PROCESS AUDIT** (Read-only investigation of LaunchAgents, Daemons, and Terminal-Wall launchers).
