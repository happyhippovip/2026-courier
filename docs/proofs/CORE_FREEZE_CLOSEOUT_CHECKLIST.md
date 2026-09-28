# CORE FREEZE CLOSEOUT CHECKLIST

## Requirements
Core functionality must be rigidly frozen prior to authorizing physical run testing on the precise Candidate SHA. This document tracks remaining open slots.

## Readiness Slots
- [x] **Ledger**: 100% Reconciled
- [x] **Agent Queues**: Cleared
- [x] **Run 1 Preparation**: MAC_HNI_01..10 Complete
- [x] **Run 2 Preparation**: MAC_HNI_11..15 Complete
- [x] **Runtime Safety**: MAC_HNI_17..20 Complete
- [x] **Proof Assembly**: MAC_HNI_21 Complete
- [ ] **Exact Candidate Source Binding**: MAC_HNI_16 (WAITING_FOR_DURABILITY_ON_FINAL_SHA)
- [ ] **Windows Codex Authorization**: PRE_CODEX_STATE=DURABILITY_PENDING (External Blocker)
- [ ] **Physical Execution Approval**: Pending Windows resolution.

## Finalization
No further changes are permitted to the Core logic of Courier before RUN 1. Once `FINAL_SHA` is durable, MAC_HNI_16 will bind it, and the system will proceed to physical execution via the scripts in `scripts/run1_physical/` and `scripts/run2_physical/`.
