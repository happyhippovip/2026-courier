# PERMANENT CRASH-PROOF RECOVERY & IDEMPOTENT CONTINUATION POLICY
**Authority**: Windows Courier Execution Lane (`WINDOWS_PARALLEL_VALUE_ENGINE`)  
**Scope**: All autonomous Windows operations, background workers, and session transitions.  
**Canonical Runtime**: `courier/chief/crash_proof_recovery.py`  
**Bootstrap Entrypoint**: `uv run python -m courier.chief.bootstrap`

---

## 1. Permanent Invariant: Session Disconnect != State Loss
- **The Chat is NOT the database**: The conversational UI may terminate, disconnect, restart, or clear history. Courier durable state lives on disk in SQLite (`chief_control_plane.db`) and write-ahead JSON (`durable_recovery_state.json`).
- **New Agent Discovery**: Any fresh Antigravity session recovers the full mission by running `uv run python -m courier.chief.bootstrap`. The human does NOT need to re-paste instructions or reconstruct previous tasks.

---

## 2. Write-Ahead Checkpoint Rules
1. **Pre-Execution**: Before running any candidate work, persist task identity, version, and acceptance criteria with status `RUNNING` and a writer lease.
2. **In-Flight Progress**: If a task produces intermediate side-effects or artifacts, checkpoint evidence to disk.
3. **Pre-Verification**: Persist result evidence with status `RESULT_READY` before invoking Result Customs.
4. **Post-Verification**: Once verified, commit completion to SQLite, register the semantic SHA-256 fingerprint in `DO_NOT_REPEAT`, and select the next safe candidate.

---

## 3. Idempotent `weiter` Contract
Every bare `weiter`, `Weiter`, `continue`, or `go` means:
```
RECONCILE_CURRENT_DURABLE_STATE()
```
It **NEVER** means:
- Re-running the previous task (`DO_NOT_REPEAT` prevents replay)
- Spawning a duplicate writer if one is already `RUNNING`
- Inventing unverified tasks or reports
- Rerunning verified commands

### Expected Transition Matrix:
| State | Incoming Signal | Action |
|---|---|---|
| Task A `RUNNING` (alive worker) | `weiter` | Suppress duplicate continuation; monitor in-flight work. |
| Task A `RUNNING` (dead worker) | `weiter` | Classify `INTERRUPTED`; reconcile effect or resume exactly once. |
| Task A `VERIFIED` | `weiter` | Suppress replay; advance to successor Task B. |
| Task A `VERIFIED` | 10× `weiter` | 0 duplicate tasks created (`TASKS_DUPLICATED = 0`). |

---

## 4. Crash-Loop Protection
- Tracks `same_task_recovery_count`.
- If a task crashes or triggers server interruption more than 3 consecutive times:
  - Mark task `BLOCKED` with reason `CRASH_LOOP_DETECTED`.
  - Do NOT retry indefinitely.
  - Automatically advance to an independent safe candidate from the portfolio.

---

## 5. Resource & Long-Output Guard
- **No Fragile Daemons**: Commands run with bounded synchronous timeouts (`IsDaemon: false`).
- **No Console Flooding**: Large outputs are written to disk logs and summarized in compact stdout to prevent Electron UI buffer saturation and disconnects.
- **Thermal Cause**: Classified as `UNPROVEN` unless validated by hardware sensor data.

---

## 6. Mac Scope Exclusion & Zero-Spend Invariant
- **Mac Scope Protected**: Zero writes to `supervisor_standalone.py`, `customs_agent.py`, `coordination/mac_to_windows`, or `universuX`.
- **Payment & Publishing Parked**: Payment gateways, external advertising, outreach, and Show HN submissions remain `PARKED_HUMAN_GATES` requiring founder authorization.
- `AUTOMATIC_SPEND_LIMIT_EUR = 0.00` strictly maintained.
