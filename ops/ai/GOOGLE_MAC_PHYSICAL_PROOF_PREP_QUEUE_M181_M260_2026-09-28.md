# Google Mac Physical Proof Prep Queue M181-M260 — 2026-09-28

Status: ACTIVE MAC PHYSICAL PROOF PREPARATION QUEUE
Host: macOS (`Darwin 25.6.0 x86_64`)
Authority: GOOGLE_CLI (Mac Hard No-Idle Finisher)
Model Class: C1
Purpose: 80 bounded, deterministic, candidate-independent verification and proof preparation tasks advancing the real Courier physical proof path without modifying candidate source or running physical tests prematurely.

## Hard Rules

- RESULT_REUSE_FIRST=YES
- MINIMUM_NECESSARY_READS=YES
- NO_BROAD_REPO_SCAN=YES
- NO_BUSYWORK=YES
- APPLICATION_SOURCE_WRITE=NO
- FINAL_CANDIDATE_WRITE=NO
- NO_PHYSICAL_RUN_1_BEFORE_READY_FOR_PHYSICAL_RUN
- NO_RUN_2_BEFORE_RUN_1_PASS
- MAX_HEAVY_JOBS=1
- CLAIM_BEFORE_ANALYSIS=YES
- Do not repeat a task after account/session change.

---

## Tasks Inventory (M181..M260)

### Group 1: Runtime, Source, Build, and Config Binding (M181..M190)
- **M181**: macOS Runtime Invariants & Darwin Kernel Binding Specification
- **M182**: Python 3 Interpreter & Standard Library Environment Isolation Verification
- **M183**: Candidate Source Scope Checksum Binding (`server/`, `scripts/`, `tests/`)
- **M184**: Dependency Tree & Standard Library Isolation Audit (No Third-Party Bleed)
- **M185**: Static Environment Variable Contract (`PORT`, `STATE_DIR`, `AUTH_TOKEN`, `VERIFIER_KEY`)
- **M186**: File Descriptor Limits & POSIX Signal Handling Specification
- **M187**: macOS Temp Directory Isolation vs In-Tree State Path Verification
- **M188**: Execution Timestamp & Monotonic Clock Invariant Check
- **M189**: Git Checkout Cleanliness & Staged File Baseline Audit
- **M190**: Candidate Source Fingerprint Verification Template

### Group 2: Artifact, Hash, and Event Evidence (M191..M200)
- **M191**: Artifact Storage Path Schema & Directory Hierarchy Layout
- **M192**: SHA-256 Checksum Calculation & Pre-Declaration Validation Invariants
- **M193**: Tamper-Evident Artifact Verification & Corrupted Byte Rejection Test
- **M194**: Event Log Schema & Ordered Microsecond Event Correlation Protocol
- **M195**: Immutable Append-Only Event Stream Invariant Validation
- **M196**: Task Goal Pre-Declared Hash vs Server Storage Hash Verification
- **M197**: Zero-Byte Artifact Fail-Closed Boundary & Handling
- **M198**: Multiple Artifact Multipart Hash Aggregation Specification
- **M199**: Evidence Index File Formats & Linking Standards (`.evidence.json`)
- **M200**: Hash Chain Continuity & Cross-Verification against Ledger

### Group 3: Process, Port, State, and Log Ownership (M201..M210)
- **M201**: Port 8081 Allocation, Exclusive Binding & Contention Prevention
- **M202**: Server Process Lifecycle & PID File Ownership (`server/state/staging.pid`)
- **M203**: Worker Process Execution Semantics & Child Process Clean-Termination
- **M204**: Independent Verifier Process Boundary & Separate Memory Space
- **M205**: State Directory Sandbox Isolation (`server/state/isolated_run1`)
- **M206**: Log File Isolation & Standard Output/Error Redirection (`logs/run1_*.log`)
- **M207**: Orphan Process Detection & Clean Cleanup Traps (`SIGTERM`/`SIGKILL`)
- **M208**: Cross-Run State Reset & Zero-Leakage Directory Scrubber
- **M209**: Port Availability Preflight Check Script Specification
- **M210**: Multi-Process Non-Interference Verification under `MAX_HEAVY_JOBS=1`

### Group 4: Restart and No-Replay Matrix (M211..M220)
- **M211**: RUN_1 Task A Single-Execution Invariant Proof
- **M212**: State Persistence Cutpoint Specification between Task A and Task B
- **M213**: Server Crash Simulation & Hard-Kill Injection Point Definition
- **M214**: RUN_2 Restart Preconditions & Initial State Validation
- **M215**: Task A Replay Prohibition & Idempotent No-Op Assertion
- **M216**: Task B Continuation & Uncompleted Dispatch Recovery
- **M217**: Duplicate Dispatch Rejection & Stale Token Invalidation
- **M218**: SQLite Database Crash Recovery & Journal Mode Verification (`WAL`)
- **M219**: 12-Case Matrix Failure Semantics under Abrupt Disconnection
- **M220**: End-to-End Restart Recovery Verification Matrix

### Group 5: Proof Card Fields & Core Freeze Fields (M221..M230)
- **M221**: Proof Card Hardware Architecture Field Specification (`x86_64` / `arm64`)
- **M222**: Proof Card Kernel & OS Version Extraction (`uname -v` / `sw_vers`)
- **M223**: Proof Card Cryptographic Hash Algorithm Invariant (`SHA-256`)
- **M224**: Proof Card Autonomy Grade A4 Metrics Aggregation (`HUMAN_RELAYS=0`)
- **M225**: Proof Card Test Suite Target Matrix Invariants (44 Tests, `SKIPPED=0`)
- **M226**: Core Freeze Candidate-Independent Field Definition & Freezing Protocol
- **M227**: Core Freeze Code Hygiene Checklist (No Trailing Whitespace, Clean Diffs)
- **M228**: Core Freeze Dependency Lock & Frozen Git Tag Protocol (`git tag`)
- **M229**: Core Freeze Post-Verification Security Lockout Rule
- **M230**: Candidate-Sensitive Proof Card Field Injection Template

### Group 6: Cross-Host, Provider, and Session Continuity (M231..M240)
- **M231**: Windows Central Writer vs Mac Verifier Handoff Contract
- **M232**: Cross-Host SHA-256 Canonical Representation Compatibility (CRLF/LF)
- **M233**: Provider-Agnostic Task Claim Lease Representation (`ops/ai/wall_claims`)
- **M234**: Session Interruption Recovery & In-Flight Claim Release Protocol
- **M235**: Asynchronous Event Log Synchronization between Windows and Mac
- **M236**: Cross-Provider Result Format Uniformity (`ops/ai/wall_results/*.md`)
- **M237**: Network Disconnection Resilience during Remote Git Resolution
- **M238**: Multi-Session State Serialization & Session Cache Invalidation
- **M239**: Central Writer Conflict Resolution & Truth Attribution Hierarchy
- **M240**: Complete Cross-Host Continuity Attestation Template

### Group 7: Result Cache, Claim Lease, and Harvest Integrity (M241..M250)
- **M241**: SQLite Blockchain Ledger Hash Chain Verification Algorithm
- **M242**: Ledger Block Invariant Audit (Previous Hash, Block Hash, SHA-256)
- **M243**: Result Cache Deduplication & Redundant Run Suppression
- **M244**: Claim Lease Expiry & Dead Worker Reclamation Logic
- **M245**: Harvest Engine Conflict Resolution & Double-Claim Prevention
- **M246**: Non-Interference Lock Validation across Parallel Subagents
- **M247**: No-Tight-Polling & Exponential Backoff Contract Verification
- **M248**: Ledger JSONL to SQLite Synchronization & Reconciliation Engine
- **M249**: Corrupted Result Quarantine Protocol & Audit Alert Generation
- **M250**: Comprehensive Ledger & Claim Integrity Diagnostic Tooling

### Group 8: Pilot Prep & Later Update/Capability Prep (M251..M260)
- **M251**: Post-Core Freeze Pilot Onboarding Boundary & Scope Isolation
- **M252**: User Repository Ingestion Contract & Zero-Trust Sandbox Isolation
- **M253**: Pilot Telemetry & Autonomous Performance Metric Collector
- **M254**: Pilot Issue Categorization & Non-Disruptive Feedback Channel
- **M255**: Pilot Completion Verification & Value Metric Measurement
- **M256**: Product Shell Architectural Lock & Scope Demarcation
- **M257**: Shared Capability Update Fabric Handoff Boundary (Post-Pilot)
- **M258**: Cryptographic Agility & Post-Quantum Algorithm Readiness Inventory
- **M259**: Commercial Pilot Security Auditing & Data Privacy Assurance
- **M260**: Final Master Proof Readiness Attestation for RUN_1 & RUN_2
