# Courier 1.0 Release Notes

Welcome to the **Courier 1.0** release notes!

Courier 1.0 marks the first general availability release candidate of the **Courier Autonomous Multi-Worker Workflow Orchestration Platform**. This milestone transforms complex, multi-step engineering and research goals into deterministic, self-healing, verifiable execution graphs spanning heterogeneous operating systems (macOS, Windows, and Linux).

---

## Highlights & Milestone Summary

Courier 1.0 represents months of architectural maturation focused on five core pillars: **Autonomy**, **Determinism**, **Host Safety**, **Cryptographic Verifiability**, and **Cross-Platform Resilience**.

- **Cross-Platform Multi-Worker Coordination**: Native, concurrent execution daemons supporting macOS (POSIX) and Windows (PowerShell/CMD) with dynamic capability negotiation.
- **Strict Identity Binding Chain**: End-to-end provenance tracing every operation from `goal_id` down to signed `attestation_id`.
- **Two-Phase Execution & Segregation of Verification**: Hard enforcement that task producers can never verify their own work (`producer_principal != verifier_principal`).
- **Cannon Execution Engine**: Durable task magazine, bounded prefetch, fencing token-based scope ownership, and emergency safety cutoffs.
- **Fail-Closed Governance & Zero-Spend Boundary**: Unconditional 0.00 EUR autonomous expenditure cap and fail-closed state validation.
- **Visual Agent HQ Dashboard**: Real-time observability plane providing queue introspection, worker metrics, and interactive goal tracking on port `8080`.
- **Fast Verification Ladder**: Sub-second pre-flight checks (`verify_autonomous_readiness.py` in `<0.05s`) coupled with deterministic multi-level verification oracles.

---

## Major Features in Version 1.0

### 1. Heterogeneous Multi-Worker Daemon Architecture

Courier 1.0 introduces hardened worker daemons capable of operating headlessly across diverse physical and virtual environments:

- **macOS Worker Daemon (`scripts/mac_worker/daemon.py`)**:
  - Full POSIX process tree supervision with process group tracking (`ACTIVE_PGIDS`).
  - Native power-state assertion using `caffeinate` to prevent system sleep during long-running tasks.
  - Multi-engine agent runner supporting Google Antigravity (`agy`), GitHub Copilot CLI (`gh copilot`), and native shell execution.
  - Autonomous non-blocking command execution via `--dangerously-skip-permissions` and sandbox bypass configurations.
- **Windows Worker Daemon (`scripts/windows_worker/daemon.py`)**:
  - Native PowerShell and CMD execution pipelines.
  - Robust UTF-8 stdin instruction streaming to eliminate encoding anomalies in terminal wrappers.
  - Windows Job Object management ensuring complete process hierarchy teardown upon task termination.
- **Capability-Based Task Routing**:
  - Dynamic worker registration advertising supported platforms, execution tools (`mac`, `windows`, `antigravity`, `copilot`, `bash`, `python`), and cost tiers.
  - Automated task assignment matching required capabilities and resource leases.

### 2. End-to-End Task Lifecycle & Identity Binding

Task execution in Courier 1.0 is strictly governed by a tamper-proof identity chain:

$$\text{goal\_id} \longrightarrow \text{task\_id} \longrightarrow \text{attempt\_id} \longrightarrow \text{dispatch\_id} \longrightarrow \text{execution\_ref} \longrightarrow \text{result\_id} \longrightarrow \text{attestation\_id}$$

- **Attempt & Dispatch Tracking**: Every retry or worker claim generates an isolated attempt ID and dispatch ID, preventing replay attacks or stale result submissions.
- **Cryptographic Artifact Proofs**: Deliverables are indexed with SHA-256 hashes immediately upon worker completion and verified independently against disk contents.
- **State Machine Integrity**: Complete enforcement of the canonical 10-state lifecycle:
  `QUEUED` $\to$ `DISPATCHED` $\to$ `RESULT_RECEIVED` $\to$ `RECONCILED` (or `RECONCILED_PENDING_MERGE`), with explicit handling for `WAITING_PROVIDER`, `BLOCKED_TRANSIENT`, and `HUMAN_REQUIRED`.

### 3. Independent Verification & Governance Plane

Courier 1.0 eliminates self-reporting bias in autonomous workflows through physical, independent verification:

- **Principal Segregation**: The central coordinator enforces distinct authorization keys for workers (`COURIER_API_KEY`) and verifiers (`COURIER_VERIFIER_API_KEY`). Self-attestation attempts receive an immediate `403 Forbidden`.
- **Durable Attestation Receipts**: Verification creates immutable attestation records containing producer/verifier fingerprints, SHA-256 result digests, and timestamps accessible via `GET /attestations/<attestation_id>`.
- **Protected Code Merge Gates**: Tasks touching critical kernel paths, authentication models, or spend mechanisms transition to `RECONCILED_PENDING_MERGE` and require explicit human or lead verifier approval via `/tasks/approve_merge`.

### 4. Cannon Engine & Resilient Task Queue

The high-throughput **Cannon Engine** powers dependable batch processing and continuous workflow execution:

- **Durable Streaming Magazine**: Disk-backed queue persistence preventing state loss during daemon restarts or network disruptions.
- **Mutable Scope Ownership with Fencing Tokens**: Monotonically increasing epoch counters guard against split-brain mutations across distributed worker threads.
- **Anti-Collision Resource Leases**: Exclusive locks (`exclusive_resources`) prevent concurrent mutations of shared files or repositories.
- **Emergency Stop Mechanism (`cannon_yolo`)**: Immediate, fail-safe kill switch to freeze queue dispatching and safely drain running jobs upon system alerts.

### 5. Host Safety & Autonomous Resource Governance

Host stability and financial boundaries are hard-coded invariants in Courier 1.0:

- **Strict 0.00 EUR Autonomous Spend Cap**: Unattended agents cannot initiate billable API calls or provision cloud resources without traversing an authenticated `HUMAN_GATE`.
- **Single Heavy Process Concurrency (`MAX_HEAVY_JOBS = 1`)**: Strict throttling guarantees that only one heavy compute task (e.g. full test regressions or large builds) runs on a host simultaneously.
- **Rate Limit & Quota Resilience (`WAITING_PROVIDER`)**: Built-in exponential backoff automatically transitions tasks to `WAITING_PROVIDER` when upstream LLM rate limits (HTTP 429 / resource exhaustion) are encountered, resuming smoothly without consuming retry quotas.
- **Stale Worker Quarantine**: Workers failing to report heartbeats within 300 seconds have their dispatched tasks safely placed into `HUMAN_REQUIRED` rather than blindly re-dispatched, preventing duplicate external side effects.

### 6. Visual Agent HQ Dashboard

Courier 1.0 ships with a lightweight, zero-dependency web dashboard:

- **Real-Time Topology View**: Inspect active goals, queued tasks, registered worker health, and attestation ledgers.
- **Live System Metrics**: Monitor task throughput, failure rates, and token consumption efficiency.
- **Emergency Controls**: Pause, resume, or abort workflows directly through the visual interface.

---

## Detailed Improvements & Bug Fixes in 1.0

### Core Coordination & API
- **Atomic State Persistence**: Replaced direct file overwrites with an atomic `NamedTemporaryFile` + `fsync()` + `os.replace()` pattern, completely eliminating 0-byte state file corruptions during sudden terminations.
- **Key Segregation Enforcement**: Hardened server initialization to reject shared or default development keys (`dev-secret-key`) with `503 Service Unavailable`.
- **Runtime SHA Alignment**: Added runtime Git SHA negotiation (`426 Upgrade Required`) to ensure workers and the central coordinator run synchronized code versions.
- **Merge Approval False-Positive Resolution**: Corrected validation logic in `/tasks/approve_merge` that previously misidentified legitimate multi-path dependencies as security violations.

### Worker Daemons & Cross-Platform Engine
- **Windows PowerShell Stdin Streaming**: Replaced CLI argument interpolation with direct UTF-8 stdin piping, resolving Unicode and quote escape errors in complex agent instructions.
- **Extended Autonomous Task Timeout**: Expanded worker execution timeouts from 300 seconds to 3600 seconds (`1 hour`) to accommodate complex, deep-thinking reasoning agents.
- **Redundant Wrapper Removal**: Deprecated fragile launcher scripts (`start.bat`, `stop.bat`, `start.py`) in favor of direct, unified daemon entry points.
- **Darwin Resource Bounds**: Adjusted filesystem caching and process inspection routines on macOS Darwin to prevent false positives in worker liveness detection.

### Fast Verification & Testing
- **Fast Verification Ladder**: Standardized development workflows into four tiers:
  1. *Level 1*: Targeted unit test (`<1s`)
  2. *Level 2*: Targeted module test (`<5s`)
  3. *Level 3*: Acceptance / crash safety oracles (`<30s`)
  4. *Level 4*: Milestone regression suite (bounded, single-job)
- **Pre-Flight Readiness Check**: Introduced `scripts/verify_autonomous_readiness.py`, completing full environment sanity checks in under 50 milliseconds.
- **Concurrency Test Suite**: Added `test_turbo_queue_concurrency.py` verifying race-free task claims and dependency cascades using execution barriers.

---

## System Requirements & Supported Platforms

| Platform | Support Tier | Worker Daemon | Notes |
| :--- | :--- | :--- | :--- |
| **macOS (Apple Silicon & Intel)** | **Tier 1 (Primary)** | `scripts/mac_worker/daemon.py` | Full support with `caffeinate` and POSIX process supervision. |
| **Windows 10 / 11 / Server** | **Tier 1 (Primary)** | `scripts/windows_worker/daemon.py` | Full support via PowerShell and Windows Job Objects. |
| **Linux (Ubuntu, Debian, RHEL)** | **Tier 2 (Supported)** | POSIX Worker Daemon | Fully compatible using standard POSIX worker configurations. |

### Minimum Software Prerequisites
- **Python**: 3.9+ (Python 3.10 or 3.11 recommended)
- **Git**: 2.30+
- **Agent Runtimes (Optional based on tasks)**:
  - Google Antigravity CLI (`agy`)
  - GitHub Copilot CLI (`gh copilot`)

---

## Upgrade & Migration Guide

### 1. Event Schema Upgrade (v1 $\to$ v2)
Pre-1.0 event envelopes using schema version 1 are now deprecated. Courier 1.0 requires version 2 envelopes adhering to `courier_event.schema.json`:
- Ensure custom event publishers provide `message_id`, `correlation_id`, `task_id`, and `payload_hash`.
- Terminal events (`RESULT`, `ACK`, `BLOCKED`) must record `parent_id` matching the initial `TASK` message ID.

### 2. Environment Configuration
Update your deployment environment variables to reflect the new key segregation rules:

```bash
# Central Server Configuration
export COURIER_HOST="127.0.0.1"
export COURIER_PORT=8080
export COURIER_API_KEY="generate-strong-worker-key"
export COURIER_VERIFIER_API_KEY="generate-strong-verifier-key-different-from-worker"

# Worker Node Configuration
export COURIER_SERVER="http://127.0.0.1:8080"
export COURIER_API_KEY="generate-strong-worker-key"
export WORKER_ID="MAC-WORKER-PRIMARY"
```

> [!WARNING]
> In Courier 1.0, setting `COURIER_VERIFIER_API_KEY` identical to `COURIER_API_KEY` will trigger an immediate fail-closed shutdown of the central server.

---

## Forward-Only Roadmap (Post-1.0)

With the core coordination engine and multi-worker lifecycle proven in Version 1.0, subsequent releases will deliver:

- **Solo Pilot Commercial Integration (P4)**: End-to-end billing integration and commercial pilot workflows with automated token metering.
- **Autonomous Multi-Agent Communities (P5)**: Federated peer-to-peer task delegation across distributed organization clusters.
- **Dynamic Cost Optimization Engine (P6)**: Predictive model escalation routing simple tasks to lightweight local models and reserving high-tier reasoning engines for complex tasks.
- **Remote Cloud Lakehouse Catalogs**: Native connectors for streaming event synchronization and remote catalog federation.

---

## Related Documentation

- [Welcome & Overview](index.md)
- [Central API Reference](api.md)
- [Contributing Guidelines](contributing.md)
- [Billing & Token Governance](billing.md)
- [Setup Guide](setup.md)
- [Architecture Deep Dive](architecture.md)
- [Security Policies](security.md)
- [Frequently Asked Questions](faq.md)

---

*Courier 1.0: Start with an idea. Let autonomous coordination carry it across the finish line.*
