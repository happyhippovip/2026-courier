# Courier Symphony Windows (v1.0.0-rc1)

**Autonomous Multi-Lane Coordination & Sovereign Execution Kernel**

Courier Symphony Windows is an autonomous, deterministic, multi-lane coordination and execution runtime designed for sovereign agent operations. It provides zero-copy inter-agent dispatch, fenced mutex leases, crash-proof recovery, and rigorous two-level task closure verification without requiring continuous human intervention ("zero human clock").

---

## Architecture & Subsystems

1. **Control Plane (`courier.chief.control_plane`)**:
   - Single-writer SQLite persistence engine.
   - Centralized finding, patch, and task registry.
   - Durable monotonic state generation and audit ledger.

2. **Operating Constitution (`WINDOWS_COURIER_OPERATING_CONSTITUTION.json`)**:
   - Canonical 34-article operating governance policy.
   - Invariants: `AUTONOMOUS_SPEND_LIMIT_EUR = 0.00`, fail-closed safety, strict Mac scope isolation.

3. **Result Customs & Two-Level Done (`courier.chief.result_customs`, `courier.chief.closure_gate`)**:
   - `company_local_step_erledigt` (Windows local evidence verified) vs `company_gesamtaufgabe_erledigt` (global cross-host convergence).
   - Independent verification of physical disk artifacts and zero false completion claims.

4. **Fenced Mutex & Crash-Proof Recovery (`courier.chief.fenced_mutex`, `courier.chief.crash_proof_recovery`)**:
   - Distributed leasing with monotonic epochs, heartbeats, and safe zombie lease reclamation.
   - Subprocess crash-boundary recovery with idempotency guarantees (at-most-once physical execution).

5. **Delta Engine & Zero-Copy Ingestion (`courier.chief.delta_engine`, `courier.chief.ingestor`)**:
   - Multi-lane state reconciliation across Windows and remote nodes.
   - Real-time delta reports generated in both structured JSON and human-readable Markdown.

---

## System Requirements

- **Operating System**: Windows 10, Windows 11, or Windows Server 2019+ (runtime core is cross-platform portable).
- **Python**: Python 3.10, 3.11, or 3.12.
- **Dependencies**: Zero external pip packages required for core chief operations (standard library only: `sqlite3`, `hashlib`, `json`, `subprocess`, `argparse`).

---

## Quickstart

### 1. Autonomous Standalone Self-Test
Run the built-in self-test to verify all core subsystems in an isolated temporary clean room:
```powershell
python SELF_TEST.py
```
Expected output:
```
=================================================================
  COURIER SYMPHONY WINDOWS V1.0.0-RC1 — AUTONOMOUS SELF-TEST
=================================================================
[*] [SELF-TEST] Running: 1. Version Introspection & Parity ... PASS
[*] [SELF-TEST] Running: 2. Operating Constitution Verification ... PASS
[*] [SELF-TEST] Running: 3. Health Diagnostic Engine ... PASS
[*] [SELF-TEST] Running: 4. Fenced Mutex Acquisition & Safety ... PASS
[*] [SELF-TEST] Running: 5. End-to-End Control Plane Ingest & Delta Cycle ... PASS
[*] [SELF-TEST] Running: 6. CLI Subcommand Registration ... PASS
=================================================================
  RESULT: ALL 6/6 CORE SUBSYSTEM VERIFICATIONS PASSED
  STATUS: V1_SELF_TEST_SUCCESSFUL
=================================================================
```

### 2. Runtime Health Diagnostic
Check database integrity, constitution validity, and runtime filesystem writability:
```powershell
python -m courier.chief.cli health
```
Or for machine-readable JSON:
```powershell
python -m courier.chief.cli health --json
```

### 3. Version & Build Introspection
Inspect canonical release metadata:
```powershell
python -m courier.chief.cli version
```

---

## CLI Reference

The Courier Chief CLI (`courier.chief.cli`) serves as the primary administration and daemon entrypoint:

| Command | Description |
|---|---|
| `version [--json]` | Displays release version, build date, git commit, Python runtime, and constitution status. |
| `health [--json]` | Executes non-destructive health checks (database integrity, constitution, filesystem writability). |
| `status` | Displays registered findings, patches, active tasks, and current resource locks. |
| `delta` | Computes and displays the latest multi-lane reconciliation delta. |
| `ingest [--dir DIR]` | Scans and ingests handoff envelopes from agents into the SQLite control plane. |
| `dispatch --target LANE` | Generates a zero-copy prompt package for dispatching work to target agent lanes. |
| `cycle [--goal GOAL] [--max-steps N]` | Runs autonomous execution cycles until quiescence or step limit. |
| `reconcile` | Reconciles local Windows tasks and certifies quiescent state. |
| `diagnostic` | Emits complete diagnostic report including watermark, locks, and active blockers. |

---

## Environment Configuration

Courier dynamically resolves workspace paths relative to its module root, but honors the following environment overrides:

| Variable | Description | Default |
|---|---|---|
| `COURIER_WORKSPACE_ROOT` | Root directory of the repository | Auto-detected parent directory |
| `COURIER_DB_PATH` | Path to `chief_control_plane.db` | `<WORKSPACE_ROOT>/courier/chief_control_plane.db` |
| `COURIER_HANDOFFS_DIR` | Directory containing agent handoff files | `<WORKSPACE_ROOT>/courier-handoffs/windows` |
| `COURIER_RUNTIME_DIR` | Temporary scratch and lease runtime directory | `<WORKSPACE_ROOT>/courier/runtime` |
| `COURIER_DISPATCH_DIR` | Dispatch package drop folder | `<WORKSPACE_ROOT>/courier/dispatch` |

---

## Security & Isolation Invariants

- **Autonomous Spend Limit**: `EUR 0.00`. Real financial transactions, credit card operations, and external API payments require explicit human cryptographic sign-off.
- **Strict Host Scope Reservation**: Mac active scopes (`courier/mac/`, `universux/`, `coordination/mac_to_windows`) are strictly isolated and protected from Windows worker modification.
- **Fail-Closed Gate**: Any missing required field, ambiguous status, or unverified metric causes immediate rejection at Result Customs.
- **Zero Path Leakage**: Release builds contain zero hardcoded developer paths or temporary scratch references.
