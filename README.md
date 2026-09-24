# 2026-Courier — Autonomous Multi-Agent Orchestration

**Courier** is an autonomous multi-agent task orchestration system designed for safe, federated execution across disparate machines, OS platforms, and language models (e.g., Google-Antigravity on Mac, Opus on Windows).

## 🏛️ System Architecture

Courier separates the **Planner/Orchestrator (Server)** from the **Executors (Workers)**.

1. **Central Server (`server/app.py`)**
   - Holds the single source of truth: `server/state/central_state.json`.
   - Dispatches tasks based on required capabilities (e.g., `mac`, `windows`).
   - Reconciles results via `/tasks/result`.
   
2. **Agent Handoff Ledger (`agent_handoff_ledger.json`)**
   - Cryptographically hashed, Git-tracked asynchronous queue.
   - Prevents split-brain by validating `CURRENT_SHA` and `RUNTIME_IDENTITY`.
   - Read/written by `scripts/courier_continue.py`.

3. **Workers (`scripts/mac_worker/daemon.py`, Windows Worker)**
   - Long-polling agents that fetch tasks, execute them locally, and return results.
   - Strictly isolated by capability tags.

## 🚀 Execution Masterplan (P0 - P6)

The project is currently governed by the **OPUS Masterplan** (`docs/plans/COURIER_EXECUTION_MASTERPLAN_2026-09-24.md`).

- **P0-P2:** Stabilization, Handoff Ledger integrity, and canonical authority (Completed).
- **P3 (Current):** Real Goal Execution with >= 2 Workers (Mac + Windows).
- **P4:** Full Solo-Pilot (Documentation Generation).
- **P5:** Product Extensions (Communities, Chats, Group Discovery).
- **P6:** Economics and Pricing validation.

## 🔒 Hard Safety Policies

- **No Standby on Missing Access:** Agents continue to execute safe tasks and return `PERSISTENCE_PENDING` payloads.
- **Strict Scope Boundaries:** Mac workers do not impersonate Windows workers.
- **Fail-Closed Security:** Corrupt state files, missing PIDs, or unverified tokens fail closed immediately.
- **No Unattended Code Merges:** `approve_merge` requires human review unless strictly isolated.

## 📁 Repository Directory Structure

- `server/` — Flask orchestration engine and `central_state.json`.
- `scripts/` — Workers (`mac_worker/`), CLI (`courier_continue.py`), and Ledger tools.
- `docs/` — Architecture, plans (`docs/plans/`), marketing, and public documentation.
- `tests/` — Automated test suites.
