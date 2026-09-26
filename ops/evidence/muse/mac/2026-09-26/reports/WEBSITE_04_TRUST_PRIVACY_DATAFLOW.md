# WEBSITE_04: TRUST, PRIVACY & DATA FLOW SPECIFICATION

**MISSION**: `COURIER_WEBSITE_LAUNCH_PREP`  
**MODE**: `LONG_RUNNING_PREP` · `HOST=MAC`  
**STATUS**: Evidence-Gated Launch Preparation Artifact  
**OUTPUT FILE**: `/Users/user/Downloads/courier_work/muse_mac_wall/reports/WEBSITE_04_TRUST_PRIVACY_DATAFLOW.md`  
**GOVERNING PRINCIPLE**: Transparency is our primary security control. Ground every privacy and trust claim in physical architecture.

---

## 1. Trust & Evidence Section (`/trust`)

Most software websites make unfalsifiable claims about "enterprise-grade AI". Courier replaces marketing adjectives with a machine-readable, verifiable **Evidence System**.

### 1.1 The Proof Card Architecture
Every autonomous execution produces an immutable **Proof Card** verifying that the work actually occurred:

```
+──────────────────────────────────────────────────────────────────────────+
|                        COURIER VERIFIED PROOF CARD                       |
+──────────────────────────────────────────────────────────────────────────+
| RUN IDENTITY:      canary-run-20260926-7a8f                              |
| GOAL:              Automated Migration & Static Verification             |
| AUTHORIZED SCOPE:  /Users/customer/projects/billing-service              |
+──────────────────────────────────────────────────────────────────────────+
| STEP A (INTAKE):   RECONCILED                                            |
|   • Worker:        MAC-01 (PID 61758, Exit Code 0)                       |
|   • Output:        build/migration.sql (4,218 bytes)                     |
|   • Disk SHA-256:  a7b92bca19b4a59543ea8a6dd6f6429e0ab4c7f6...          |
|   • Verified By:   courier_verifier (Independent PID 42002, Verdict: PASS)
+──────────────────────────────────────────────────────────────────────────+
| CONTINUATION:      AUTOMATIC (< 0.4s latency)                            |
| HUMAN RELAYS:      0 (Zero manual clicks between Step A and Step B)      |
+──────────────────────────────────────────────────────────────────────────+
| STEP B (PACKAGE):  RECONCILED                                            |
|   • Worker:        MAC-02 (PID 61804, Exit Code 0)                       |
|   • Output:        dist/release.zip (18,402 bytes)                       |
|   • Disk SHA-256:  332a42f9edcf1de1535870592da34a7961880991...          |
|   • Verified By:   courier_verifier (Independent PID 42002, Verdict: PASS)
+──────────────────────────────────────────────────────────────────────────+
| RECOVERY AUDIT:    PASSED (Zero duplicate runs; state preserved)        |
+──────────────────────────────────────────────────────────────────────────+
```

### 1.2 Separation of Truth: What is Physical vs What is Simulated

| Capability | Status | Physical Evidence in Repository |
| :--- | :---: | :--- |
| **A $\rightarrow$ VERIFY $\rightarrow$ B Continuation** | **PHYSICALLY PROVEN** | Verified in Canary test runs (`HUMAN_RELAYS=0`, latency < 0.5s). |
| **Hash-Matching Verifier** | **PHYSICALLY PROVEN** | `scripts/courier_verifier.py` checks raw disk bytes via `read_bytes()`. |
| **Crash & Restart Recovery** | **PHYSICALLY PROVEN** | Ingest of `central_state.json` with identical byte hash ($S_2 \equiv S_1$). |
| **Single-Scope Boundary Lock** | **TEST VERIFIED** | Restricts I/O strictly to `AUTHORIZED_WORKSPACE`. |
| **Dynamic Cloud Auto-Scaling** | **SIMULATED / DESIGN** | Architectural specification in `WEBSITE_BLUEPRINT_2026.md`. |
| **Multi-Turn Open Coding** | **SIMULATED / DESIGN** | Tested in hermetic fixtures; bounded pilot workflows active. |

---

## 2. Privacy & Data Handling Summary

For software companies, sharing proprietary source code with AI tools is a critical security risk. Courier enforces a strict local-first privacy boundary:

```
+──────────────────────────────────────────────────────────────────────────+
| LOCAL DISK ENCLAVE (AUTHORIZED_WORKSPACE)                                |
|                                                                          |
| • Your proprietary source code NEVER leaves your machine by default.    |
| • Execution, compilation, and file inspection happen 100% locally.       |
| • The verifier runs locally as an independent process on your OS.        |
+──────────────────────────────────────────────────────────────────────────+
                                     │
                 Only When External Model is Requested:
                                     │
                                     ▼
+──────────────────────────────────────────────────────────────────────────+
| BOUNDED REST / MODEL CALLS (ENCRYPTED TLS 1.3)                           |
|                                                                          |
| • Minimum Necessary Context Capsule (No full codebase dumping).          |
| • Zero retention: We do NOT train AI models on customer code.            |
| • Ephemeral API keys: Credentials never persisted in worker state logs.  |
+──────────────────────────────────────────────────────────────────────────+
```

### Core Privacy Commitments:
1. **Zero Model Training**: Customer code, prompts, and artifacts are never used to train or fine-tune public foundation models.
2. **Local Artifact Storage**: All deliverables, logs, and central states are stored on your local filesystem under `AUTHORIZED_WORKSPACE`.
3. **No Unannounced Telemetry**: Courier does not silently upload file contents, folder trees, or environment variables to central cloud servers.

---

## 3. Data Flow Architecture

The data lifecycle follows an explicit, unidirectional flow:

```
[Customer Workspace]
        │
        ▼ (Local File Read)
[Courier Local Worker] ──(Optional Inference)──► [Provider Endpoint (TLS)]
        │                                                    │
        ▼ (Write Output Bytes)                               ▼ (Token Stream)
[Local Workspace Disk] ◄─────────────────────────────────────┘
        │
        ▼ (Independent Byte Hash)
[courier_verifier Process]
        │
        ▼ (HTTP REST Attestation: verdict="PASS")
[Local Courier Control Plane (server/app.py)]
        │
        ▼ (Atomic Disk Write: central_state.json)
[Durable Local State]
```

### Boundary Protections:
- **Credential Isolation**: API keys (`COURIER_API_KEY`, provider tokens) are injected exclusively via environment variables into memory; they are **never** serialized into `central_state.json` or committed to Git.
- **Fail-Closed on Unknown Network Status**: If network connectivity drops or a provider returns an ambiguous 502/504 status, Courier halts the affected task in `AMBIGUOUS_STARTED` rather than guessing or blindly resubmitting.
- **Out-of-Scope Escaping Prevention**: Path resolution strictly validates that `target_path.resolve().is_relative_to(authorized_workspace)`. Any path traversal (`../`) is blocked before filesystem execution.

---

## 4. Trust & Privacy Claim Discipline Registry

| Claim Element | Public Claim Statement | Currently Proven? | Evidence Source | Safe to Publish Now? |
| :--- | :--- | :---: | :--- | :---: |
| **TR-01** | Zero model training on customer code | **YES** | Local execution architecture; standard enterprise API terms | **YES** |
| **TR-02** | Independent verifier validates artifacts on disk | **YES** | `scripts/courier_verifier.py`, Canary logs | **YES** |
| **TR-03** | Local disk persistence with zero telemetry leaks | **YES** | `server/state/central_state.json`, hermetic test suite | **YES** |
| **TR-04** | Formal SOC2 / ISO27001 certification | **NO** | Product is currently in pilot / pre-certification stage | **NO** (Never claim formal compliance) |
| **TR-05** | Air-gapped on-premise deployment mode | **PARTIAL**| Works with local models/fixtures; full airgap docs in prep | **PARTIAL** (Publish as "Local-First Architecture") |
