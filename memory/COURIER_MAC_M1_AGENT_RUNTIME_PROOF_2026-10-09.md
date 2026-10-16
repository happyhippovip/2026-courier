# Courier Symphony — Mac M1 Agent Runtime Proof Checkpoint

**Date:** 2026-10-09  
**Workkey:** MAC-V24-M1-EXISTING-AGENT-RUNTIME-PROOF  
**Host:** Mac Intel (Darwin 24.3.0, Darwin Kernel 24.3.0, Swap ~8.4 GB, RESOURCE_PAUSE active)  
**Owner:** Mac Read-Only Investigator / L1 Supervisor  
**Selected Agent:** `agent-antigravity-bridge`  

---

## 1. Trace Matrix

| Kante | Komponente | Quelle | Commit / Evidenz | Status |
|---|---|---|---|---|
| **AGENT_ID** | Identität | `scripts/run_antigravity_bridge.py` | `DEFAULT_AGENT_ID = "agent-antigravity-bridge"` | **PROVEN** |
| **CAPABILITY** | Task-Lifecycle & State-Tracker | `scripts/run_antigravity_bridge.py` | `AntigravityHookRunner`, `events/agent-states/` | **PROVEN** |
| **AUTHORITY** | Zero-Spend & Review-Router | `scripts/run_antigravity_bridge.py` | B-010 Fail-Closed Router (8/8 Tests grün) | **PROVEN** |
| **PROVIDER_ADAPTER** | Adapter-Anbindung | PR #141 `adapters/local_shell.py` | Fehlt in `run_antigravity_bridge.py` | **MISSING** |
| **WORKER** | Contained Child Process | `courier_worker/adapter_runner.py` | `ALLOWED = frozenset({"synthetic", "local_shell"})` | **PROVEN** (nach #351) |
| **TASK / DISPATCH** | Canonical Task Mint | `courier_core/controller.py` | `POST /v1/tasks` (idempotency key) | **PROVEN** |
| **RESULT_RECEIPT** | Relativer Output-Hash | `adapters/local_shell.py` | `RunResult` mit workspace-relativem Hash | **PROVEN** |
| **VERIFIER** | Fail-Closed Audit | `adapters/local_shell.py:verify` | Verifier Version 1, prüft SHA256 & Pfad | **PROVEN** |
| **CANONICAL_LEDGER** | Buchung & Release | `scripts/ledger_controller_bridge.py` | `receipt_event_fields()` setzt `FINAL / DONE` | **PROVEN** |

---

## 2. Earliest Unproven Edge & Repair

- **Earliest Unproven Edge:** `AUTHORITY → PROVIDER_ADAPTER`
- **Owner:** Lane L4 (PR #141 `adapters/local_shell.py`)
- **Actionable Gap:** `agent-antigravity-bridge` schreibt derzeit file-basierte JSON-Dateien nach `events/processed/`. Um kanonisch über Courier V1 zu laufen, muss es als Subprozess über den `local_shell`-Adapter (`params.command = [sys.executable, "scripts/run_antigravity_bridge.py", ...], params.write = "result.json"`) aufgerufen und vom Verifier auditiert werden.
