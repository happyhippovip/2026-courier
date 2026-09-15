# Courier Autonomous Live Architecture Report

**Document ID:** `AUTONOMY_LIVE_REPORT.md`  
**Execution Timestamp:** `2026-09-15T08:14:30+02:00`  
**Run Target:** `[Run: Sept 15 NIGHT SHIFT V2]`  
**Task ID:** `plan-imp-e5dc3be0`  
**Task Hash:** `ebe0e3ca50ff0d0c`  
**Target Agent:** `GEMINI`  
**Workflow Provenance:** Verified and produced autonomously via Courier multi-agent safety dispatcher and execution loop.

---

## 1. Executive Summary

This report documents the actual, verified operational architecture of the Courier autonomous orchestrator ecosystem based on live repository code, state machines, schemas, and multi-agent coordination artifacts. The Courier architecture coordinates heterogeneous workers (Google Gemini, OpenAI Codex, Deterministic CLI, and remote Windows nodes) under a zero-cost, fail-closed safety regime with deterministic result customs, fencing tokens, and cryptographic state verification.

---

## 2. Autonomous Orchestrator Architecture Overview

The orchestrator operates across tightly integrated layers spanning orchestration & control, worker routing & adaptation, and customs verification:

```mermaid
flowchart TD
    subgraph Orchestration & Control Plane
        A["Courier Daemon / Safety Dispatcher<br/>scripts/courier_daemon.py<br/>scripts/courier_safety_dispatcher.py"]
        B["Opportunity Queue & Next Safe Work Router<br/>scripts/opportunity_queue.py<br/>scripts/next_safe_work_router.py"]
        C["Live Worker Registry & Chief Brain<br/>scripts/live_worker_registry.py<br/>scripts/chief_brain.py"]
        SM["State Machines & Resource Governor<br/>scripts/useful_work_state_machine.py<br/>scripts/long_run_resource_governor.py<br/>scripts/canonical_authority.py"]
    end

    subgraph Heterogeneous Worker Fleet
        D["Google / Gemini Worker<br/>scripts/native_agy_runner.py<br/>scripts/gemini_work_dispatcher.py<br/>/Users/user/.local/bin/agy"]
        E["Codex Bridge Worker<br/>scripts/run_codex_bridge.py<br/>scripts/codex_work_dispatcher.py<br/>/Applications/ChatGPT.app/Contents/Resources/codex"]
        F["Deterministic CLI1 Worker<br/>scripts/cli_operations_autopilot.py"]
        G["Windows Remote Host (PC2)<br/>scripts/windows_work_dispatcher.py<br/>coordination/mac_to_windows/<br/>coordination/windows_to_mac/"]
    end

    subgraph Customs, Invariants & Verification
        H["Mac Result Consumer & Schema Customs<br/>scripts/mac_result_consumer.py<br/>schemas/courier_result.schema.json"]
        I["Cryptographic Fingerprint & Memory<br/>scripts/courier_experience_memory.py<br/>scripts/canonical_authority.py"]
        J["Goal Satisfaction Engine<br/>scripts/goal_satisfaction_state.py"]
    end

    A --> B
    B --> C
    C --> SM
    C --> D
    C --> E
    C --> F
    C --> G
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I
    H --> J
```

### Core Architecture Subsystems
1. **Dispatcher & Daemon Loop** (`scripts/courier_daemon.py`, `scripts/courier_safety_dispatcher.py`):
   - Polls `events/mission-queue/queue.json` and evaluates state transitions (`WAITING_AUTHORIZED_WORK`, `IN_PROGRESS`, `HUMAN_GATE`).
   - Implements watchdog protection (`NO_PROGRESS_WATCHDOG_TRIPPED`) after thresholded consecutive failures.
2. **Dynamic Work Routing & Capability Matching** (`scripts/next_safe_work_router.py`, `scripts/live_worker_registry.py`):
   - Dynamically tracks worker status classes (`AVAILABLE`, `SAFE_IDLE`, `RUNNING`, `STARTING`).
   - Dispatches safe, bounded opportunities to designated target agents without violating zero-cost or sandbox boundaries.
3. **Canonical Authority & Resource Governance** (`scripts/canonical_authority.py`, `scripts/long_run_resource_governor.py`):
   - Enforces atomic state transitions, strict lease durability, and epoch finalization.
   - Monitors CPU, memory, log growth, and process health to maintain uninterrupted long-run stability.
4. **Result Customs & Cryptographic Verification** (`scripts/mac_result_consumer.py`, `schemas/courier_result.schema.json`):
   - Enforces SHA-256 fingerprint matching (`result_fingerprint = sha256(request_id + status + observed_behavior)`).
   - Validates envelope schema, prevents replay attacks, and archives processed items into `coordination/mac_to_windows/archive/`.

---

## 3. Heterogeneous Worker Subsystems & Execution Boundaries

### 3.1 Google / Gemini Worker Subsystem
* **Binary / CLI Executable:** `/Users/user/.local/bin/agy` (Antigravity Native CLI)
* **Runner Module:** `scripts/native_agy_runner.py`
* **Adapter Function:** `create_real_gemini_adapter()` in `scripts/courier_real_worker_adapters.py`
* **Work Dispatcher:** `scripts/gemini_work_dispatcher.py`
* **Default Model:** `gemini-3.7-flash-medium`
* **Execution Characteristics:**
  - Non-interactive subprocess execution with closed `stdin` (`/dev/null`).
  - Structured output parsing (`--output-format json`).
  - Permission flags: `--dangerously-skip-permissions`.
  - Autonomous fallback & Human-gate detection for authentication barriers (`error_type == 'AUTHENTICATION_REQUIRED'`).
  - Scope: Authoritative for write/implementation missions (`implement_bounded_improvement`) and acceptance audits.

### 3.2 Codex Worker Subsystem
* **Binary / CLI Executable:** `/Applications/ChatGPT.app/Contents/Resources/codex`
* **Runner Module:** `scripts/run_codex_bridge.py`
* **Adapter Function:** `create_real_codex_adapter()` in `scripts/courier_real_worker_adapters.py`
* **Work Dispatcher:** `scripts/codex_work_dispatcher.py`
* **Visual State & Lifecycle Hooks:** `CodexVisualStateTracker` (`events/agent-states/agent-codex-bridge.json`) and `CodexHookRunner`.
* **Execution Characteristics:**
  - Strict sandboxed execution (`--sandbox read-only -C <COURIER_DIR>`).
  - Secret scanning regex filter preventing credential leakage in outputs.
  - Fail-closed write constraint: Codex is enforced read-only; write requests trigger fail-closed routing redirecting to Gemini.

### 3.3 Windows Worker Subsystem
* **Worker Identity:** `WINDOWS_PC2` (with capability roles like `WINDOWS_GOOGLE` / `WINDOWS_RELAY_VALIDATOR`)
* **Dispatcher Module:** `scripts/windows_work_dispatcher.py`
* **Cross-Host Coordination Structure:**
  - Outbound Requests: `coordination/mac_to_windows/requests/` and `coordination/mac_to_windows/MAC_CROSS_HOST_CONNECTION_HANDOFF.json`
  - Inbound Results & Claims: `coordination/windows_to_mac/results/`, `coordination/windows_to_mac/claims/`, `coordination/windows_to_mac/handoffs/`
  - Acknowledgment & Archive: `coordination/mac_to_windows/acks/`, `coordination/mac_to_windows/archive/`
  - Heartbeat Synchronization: `coordination/heartbeats/windows_heartbeat.json` & `coordination/heartbeats/mac_heartbeat.json`
* **Execution Characteristics:**
  - Atomic SMB file-based shared filesystem transport (`mac_request_producer.py` & `mac_result_consumer.py`).
  - Fencing tokens and epoch validation preventing split-brain execution across physical nodes.
  - Dual schema compatibility: Supports `windows_validation_request_id` and dynamic `content_integrity` verification against execution evidence.

### 3.4 Deterministic CLI1 Worker Subsystem
* **Worker Module:** `scripts/cli_operations_autopilot.py`
* **Execution Characteristics:**
  - In-process deterministic execution for workspace discovery, test runs, and static verification.
  - Generates reproducible proofs and state snapshots without external network dependencies.

---

## 4. Operational Status & Verification Record

| Worker Subsystem | Target Binary / Transport | Adapter State | Verification Status | Operational Role |
| :--- | :--- | :--- | :--- | :--- |
| **GEMINI** | `/Users/user/.local/bin/agy` | Active & Verified | **PASS** | Authoritative Code Implementation, Refactoring & Audits |
| **CODEX** | `/Applications/ChatGPT.app/Contents/Resources/codex` | Active & Verified | **PASS** | Sandboxed Read-Only Analysis & Codebase Exploration |
| **CLI1** | Local Python Subprocess | Active & Verified | **PASS** | Deterministic Discovery, Hygiene & Unit Test Harness |
| **WINDOWS_PC2** | File-based SMB Coordination | Active & Verified | **PASS** | Cross-Host Execution, Windows-Specific Builds & Validation |

---

## 5. Workflow Provenance

This report was generated and verified autonomously by the **Gemini Autonomous Worker** for `[Run: Sept 15 NIGHT SHIFT V2]` in execution of Task `plan-imp-e5dc3be0` (Task Hash: `ebe0e3ca50ff0d0c`).
