# Courier Symphony Windows (v1.0.0-rc1) — Operational Recovery Card

**Authoritative Fast-Reference Disaster Recovery & Sovereign Runbook**

---

## 1. System Identity & Canonical Constants

| Property | Value |
|---|---|
| **Product Name** | Courier Symphony Windows |
| **Release Tag** | `v1.0.0-rc1` |
| **Operating Constitution** | `WINDOWS_COURIER_OPERATING_CONSTITUTION.json` (34 Articles) |
| **Canonical Role** | `WINDOWS_PARALLEL_COMMERCIAL` / Sovereign Windows Execution Node |
| **Autonomous Spend Limit** | `EUR 0.00` (Strictly enforced fail-closed) |
| **Mac Isolation Boundary** | `courier/mac/`, `universux/`, `coordination/mac_to_windows` (READ-ONLY / UNTOUCHABLE) |
| **State Generation** | Monotonic integer in `chief_control_plane.db` and `quiescent_watermark` |

---

## 2. Immediate Operational Health & Diagnostics

Always run these non-destructive diagnostics first when inspecting system status or troubleshooting:

### Quick Diagnostic Triage
```powershell
# 1. Full non-destructive health audit (DB, Constitution, Runtime)
python -m courier.chief.cli health

# 2. Machine-readable JSON health report
python -m courier.chief.cli health --json

# 3. Canonical version and build introspection
python -m courier.chief.cli version

# 4. Multi-lane state reconciliation delta
python -m courier.chief.cli delta

# 5. Full control plane findings, patches, tasks, and active locks
python -m courier.chief.cli status
```

---

## 3. Disaster Recovery Procedures

### Scenario A: SQLite Database Corruption or Unclean Shutdown
**Symptom**: `python -m courier.chief.cli health` returns `UNHEALTHY` with database integrity error.

**Recovery Protocol**:
1. Terminate any running courier processes (`python`, `agy`).
2. Inspect `courier/` for recent WAL/SHM files:
   ```powershell
   ls courier/chief_control_plane.db*
   ```
3. If WAL recovery fails or database is corrupted, restore from latest clean snapshot:
   ```powershell
   cp courier/chief_control_plane.db courier/chief_control_plane.db.corrupt_backup
   cp <BACKUP_PATH>/chief_control_plane.db courier/chief_control_plane.db
   ```
4. Verify database integrity:
   ```powershell
   python -m courier.chief.cli health
   ```
5. Reconcile Windows task state:
   ```powershell
   python -m courier.chief.cli reconcile
   ```

---

### Scenario B: Stale / Zombie Fenced Mutex Leases
**Symptom**: A resource lock (`fenced_resource_locks`) remains held by a dead process PID or crashed host.

**Recovery Protocol**:
1. Check active locks:
   ```powershell
   python -m courier.chief.cli status
   ```
2. The `FencedMutexManager` automatically inspects PID liveness via Windows Win32 API (`GetExitCodeProcess` checking for code `259 STILL_ACTIVE`).
3. If the holding process has terminated or the TTL has expired, any new caller invoking `acquire()` or `attempt_steal()` will safely advance the monotonic epoch and reclaim the lock without corrupting existing transactions.
4. To inspect or clear locks programmatically in Python:
   ```python
   from courier.chief.fenced_mutex import FencedMutexManager
   fmm = FencedMutexManager()
   # Attempt safe steal of expired or dead PID lease:
   res = fmm.acquire("RESOURCE_ID", holder_id="WINDOWS_CLI_1", ttl_seconds=30)
   print(res)
   ```

---

### Scenario C: Agent Handoff Validation Rejections
**Symptom**: `python -m courier.chief.cli ingest` reports handoffs rejected with `status: REJECTED_VALIDATION`.

**Root Cause & Verification**:
The `ChiefRequestValidator` enforces Article 34 of the Operating Constitution. All incoming handoffs must contain:
1. `assignment_id` (Non-empty string matching `REQ-*` or `ASSIGN-*`)
2. `origin` (Recognized agent lane, e.g. `WINDOWS_CLI_1`, `MAC_GOOGLE`, `CODEX`)
3. `role` (Non-empty string)
4. `timestamp_utc` (Valid ISO 8601 UTC timestamp)
5. `host_os` (`WINDOWS` or `MAC`)
6. `mac_host_access` (`False` on Windows nodes)
7. `production_write_authority` (`False` on all local laboratory nodes)
8. Target files MUST NOT touch reserved Mac scopes (`courier/mac`, `universux`, `coordination/mac_to_windows`) or attempt directory traversal (`../`).

Fix the envelope JSON structure in `courier-handoffs/windows/` and re-run:
```powershell
python -m courier.chief.cli ingest
```

---

### Scenario D: High-Frequency Queue Storms (100+ Duplicate Messages)
**Symptom**: A human or automation client repeatedly queues `weiter` or bare continuation commands.

**Engine Behavior & Confirmation**:
- The `QueueCoalescer` semantically parses bare continuation keywords (`weiter`, `continue`, `go`).
- For any active generation, the 1st signal materializes exactly ONE logical continuation intent.
- Signals 2 through 100+ are absorbed with status `COALESCED_IN_FLIGHT` or `COALESCED_EXISTING_INTENT`.
- If the system is in proven quiescent state, `QuiescentQueueAbsorber` absorbs signals as `QUIESCENT_NOOP` with zero side effects.
- Confirm coalescing metrics:
  ```python
  from courier.chief.queue_coalescer import QueueCoalescer
  qc = QueueCoalescer()
  print(qc.get_metrics())
  ```

---

## 4. Emergency Autonomy Invariants Checklist

Before any mission cycle or operational deployment, verify these 5 safety invariants:

- [x] `AUTONOMOUS_SPEND_LIMIT_EUR == 0.00`
- [x] Zero network calls to paid commercial external APIs
- [x] Zero write operations outside Windows workspace boundary
- [x] Mac coordination scopes strictly isolated
- [x] Two-Level Done (`company_local_step_erledigt`) certified by Result Customs before task closure
