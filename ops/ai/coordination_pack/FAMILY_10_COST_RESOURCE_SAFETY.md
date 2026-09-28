# Family 10: Cost & Resource Safety Deterministic Controls

Status: SPECIFIED
Scope: Bounded Resource Admission, Max Heavy Jobs Guard, and Token Waste Prevention.

---

## 1. 6-Point Slot Admission Envelope

```
+-----------------------------------------------------------+
| Requested Slots: Total parallel workers attempting to run |
+-----------------------------------------------------------+
                             |
                             v
+-----------------------------------------------------------+
| Capacity Governor Check: CPU < 80%, RAM avail > 2GB,      |
| Swap < 1GB, MAX_HEAVY_JOBS <= 1 per host                  |
+-----------------------------------------------------------+
            |                               |
            v (Admitted)                    v (Shed / Backoff)
+------------------------+      +---------------------------+
| Admitted Slots         |      | Waiting / Guarded Slots   |
+------------------------+      +---------------------------+
            |
            +--> Active Slots: Currently executing tasks
            |
            +--> Reserved Interactive Slots: Kept free for UI/Chat
```

- **REQUESTED_SLOTS**: Number of worker slots configured in orchestration.
- **ADMITTED_SLOTS**: Slots granted execution token by `CapacityGovernor`.
- **ACTIVE_SLOTS**: Slots currently running task code.
- **WAITING_SLOTS**: Slots queued waiting for resource headroom.
- **GUARDED_SLOTS**: Slots held in pause state due to high machine pressure.
- **RESERVED_INTERACTIVE**: Exactly 1 slot reserved for interactive user control/status queries.
- **MAX_HEAVY_JOBS**: Strict limit of 1 per host (enforced: only one physical server/canary run at a time).

---

## 2. Token & Quota Waste Prevention Rules

| Source of Waste | Observed Hazard | Deterministic Guard |
|---|---|---|
| **Unchanged Reads** | Re-reading the entire repository at the start of each chat | Hard cost rule: `ops/ai/` truth pointer first; zero whole-repo directory scans. |
| **Duplicate Reviews** | Multiple LLM workers reviewing the exact same unchanged code | Check existing `.result.md` in `wall_results/`; if present, reuse verdict. |
| **Idle AI Polling** | LLM generating responses every 10 seconds just to ask "is it done?" | Transition to `TRUE_IDLE` with shell sleep (900s) or event-driven wakeup. |
| **Repeated Tests** | Re-running test suites without source changes | Tests only run when candidate SHA or runtime environment changes. |
| **Giant Context** | 500k-token conversation histories causing massive token consumption | Context compaction and checkpointing to durable ledger files; paste prompt fresh. |
| **Unnecessary Provider Calls** | Calling expensive models for file moving or hashing | Deterministic Python scripts handle hashing, copying, and file validation. |
