# LOCALHOST PROGRESS VIEW REQUIREMENTS V1

## Overview
Defines specifications for a lightweight, compact localhost dashboard to render the operational status of Symphony.
The dashboard reads exclusively from machine-readable progress contracts (`SYMPHONY_PROGRESS_CONTRACT_V1.json` and `SYMPHONY_PROGRESS_SNAPSHOT.json`).

## UI / Layout Architecture

### 1. Header & Hero Metric
- **Overall Progress Ring / Bar**: Prominently display **91%**.
- **Callout Text**: "9% remaining to Symphony V1".
- **Mission Badge**: Display current mission (`WINDOWS_PRODUCTION_RUNTIME_FREEZE_HANDOFF_V1`) and state (`WINDOWS_RUNTIME_FROZEN_READY_FOR_CONVERGENCE`).
- **Safety Indicator**: Strict green badge: "SPEND: €0.00 | TRADES: 0 | WALLETS: 0".

### 2. Subsystem Cards
Render a card for each of the core subsystems with percentage and progress bar:
1. **Windows Courier**: 99% (Status: PROVEN_STABLE)
2. **Windows Production Runtime**: 97% (Status: PROVEN_ENTRYPOINT_FROZEN)
3. **Safety & Governance**: 97% (Status: PROVEN_HARDENED)
4. **Restart & Resume Durability**: 97% (Status: PROVEN_DURABLE)
5. **Long-Run Autonomous Operations**: 80% (Status: PROVEN_LOCAL_CONTINUUM)
6. **Money Factory (agent-context-trimmer)**: 93% (Status: FROZEN_RC1_VERIFIED)
7. **Commercial Launch Readiness**: 95% (Status: HUMAN_GATE_LOCKED)
8. **Mac / Windows Convergence**: 70% (Status: WAITING_MAC_WRITER_CLOSURE)
9. **Commercial Revenue Proof**: 0% (Status: EUR 0 TRUTH — Target: €5.00)

### 3. Next Gate & Task
- **Next Gate**: MAC CLOSURE → CROSS-PLATFORM CONVERGENCE → JOINT CANARY
- **Next Task Status**: WAITING FOR MAC WRITER RESULT
- **Action Control**: Dispatch disabled (Safety lock active).

### 4. Human Gate Alert Card
- **Open Gate**: `GATE-EUR5-FIRST-SALE`
- **Details**: Awaiting manual human operator decision to publish `agent-context-trimmer v1.0.0` to Gumroad.
- **Requirement**: Zero automated bypass; strictly gated behind explicit coordinator action.

### 5. Visual State Color Semantics
- **GREEN**: Verified / Pass / Satisfied (e.g. 114/114 regression, 12/12 canary, 19/19 bypass, 25/25 adversarial).
- **YELLOW**: Active / Partial / Awaiting Peer (e.g. Mac writer busy, convergence handoff staged).
- **RED**: Blocked / Fail / Security Breach (e.g. spend > €0, execution uncertain fence).
- **GRAY**: Not started / Unknown.

## Data Ingestion Rules
- The view reads strictly from `SYMPHONY_PROGRESS_SNAPSHOT.json` and `SYMPHONY_PROGRESS_CONTRACT_V1.json`.
- The view must **NEVER** scrape raw prose, chat transcripts, or guess progress from log size.
