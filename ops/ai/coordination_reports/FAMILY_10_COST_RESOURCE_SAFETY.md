# Family 10: Cost & Resource Safety Controls

**Status**: ACTIVE CONTROLS VERIFIED  
**Reference**: `ops/ai/MUSE_WALL_COST_GUARD_2026-09-27.md`

---

## 1. Deterministic Slot Governance

```
REQUESTED_SLOTS (Total worker processes spawned)
  └── ADMITTED_SLOTS (Passed capacity governor: Memory > 4GB, CPU < 80%)
        ├── ACTIVE_SLOTS (Light analytical/reading processes, up to 10)
        ├── GUARDED_SLOTS (Throttled due to resource pressure)
        ├── RESERVED_SLOTS (Port 8085 preflight / Port 8081 Canary)
        └── MAX_HEAVY_JOBS = 1 (Strict singleton for live server/daemon execution)
```

- **Invariant**: Logical slots (`MAC-SLEEP-001..050`, `POST200-001..050`) are analytical, light read-only worker slots. They do NOT spawn heavy background daemons.
- **Physical Canary Guard**: Only 1 heavy Canary process may run across the node, bound to an isolated port (`8081` or `8085`).

---

## 2. Token & API Waste Elimination Audit

| Waste Vector | Observed Risk | Implemented Deterrent | Status |
|---|---|---|:---:|
| **Unchanged Reads** | Re-reading entire repo tree or unchanged documentation | Explicit file-list read contract (`MINIMUM_NECESSARY_READS=YES`) | **ELIMINATED** |
| **Duplicate Reviews** | Multiple models writing redundant review essays | Single Codex HIGH review gate; all peer workers read-only | **ENFORCED** |
| **Idle AI Polling** | Chat sessions running tight curl loops | Shell-level deterministic sleep / OS signals; AI sleeps | **ENFORCED** |
| **Repeated Tests** | Re-running full pytest suite on unchanged SHA | Targeted tests only (`tests/test_p3_server_idempotency.py`, `tests/test_artifact_upload_flow.py`) | **ENFORCED** |
| **Giant Context** | Token context bloat leading to degradation | Periodic `/clear` + reload from durable ledger (`ledger.jsonl`) | **ENFORCED** |
| **Unnecessary Calls** | Speculative task creation to avoid idleness | `TRUE_IDLE` state transition when unworked queue = 0 | **ENFORCED** |
