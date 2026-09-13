# Courier Symphony Windows V1 Release Candidate Report

**Release Tag**: `v1.0.0-rc1`  
**Product**: Courier Symphony Windows  
**Build Date**: 2026-09-13  
**Status**: **PROVEN, AUDITED & ACCEPTANCE READY**

---

## 1. Release Identification & Integrity

| Artifact | Details |
|---|---|
| **Canonical Product Name** | Courier Symphony Windows |
| **Version** | `1.0.0-rc1` |
| **Release Tag** | `v1.0.0-rc1` |
| **Package Archive** | `courier/dist/courier_symphony_v1.0.0-rc1.zip` |
| **Package Byte Size** | ~164 KB (164,154 bytes compressed) |
| **Package SHA256** | `616b2e957304e13240e0cc2f09e19bc08c045f9bea4ae9b36b4dace9f3acd0e7` |
| **Manifest Checksum** | `f38cd3c4300f2c1dc814c6ac6fd79db533c5d5924cc89a0b106fd2109ec6bafa` |
| **Git Commit** | `1f309b1d7f4c4d27841c5979d78074dadf1407e7` (plus V1 release commits) |
| **Operating Constitution** | `WINDOWS_COURIER_OPERATING_CONSTITUTION.json` (34 Articles, ACTIVE) |
| **State Watermark** | Generation 126 (`NO_REAL_GAP`, `QUIESCENT_WAKEABLE`) |

---

## 2. Release Candidate Acceptance Courts Matrix (6/6 Passed)

The release archive was subjected to the complete 6-court automated acceptance campaign executed inside disposable clean-room environments (`run_v1_release_candidate_courts.py`):

| Court ID | Domain | Execution Condition | Result | Evidence |
|---|---|---|---|---|
| **COURT-01** | **Fresh Package Installation** | Extracted `.zip` to fresh temp directory; zero configuration; zero env tweaks. | **PASS** | `manual_fixes_required = 0`, `version = 1.0.0-rc1`, `health = HEALTHY`. |
| **COURT-02** | **Autonomous A→B→C Execution** | Task A execution, injected hard crash (exit code 42) in Task B, Process 2 resume. | **PASS** | `process_1 = 42`, `process_2 = 0`, `real_physical_effects_b = 1`, `zero_intermediate_human_signals = True`. |
| **COURT-03** | **Upgrade Simulation** | Upgraded code from rc1 to rc2 over live populated database with state generation 126. | **PASS** | `data_loss_detected = False`, `preserved_state_generation = 126`, `upgraded_version = 1.0.0-rc2`. |
| **COURT-04** | **Disaster Recovery & Rollback** | Injected simulated corruption / disk failure; executed snapshot restoration. | **PASS** | `corruption_detected = True`, `rollback_restored_health = True`, `recovered_integrity = ok`. |
| **COURT-05** | **100 Duplicate Input Storm** | 100 rapid-fire `weiter` continuation signals delivered to installed runtime. | **PASS** | `burst_messages_evaluated = 100`, `burst_intents_created = 1`, `burst_coalesced = 99`, `absorber_replays_absorbed = 100`. |
| **COURT-06** | **Security & Path Portability** | Scanned all release archive members and source files for hardcoded paths and private keys. | **PASS** | `forbidden_patterns_scanned = 4`, `archive_members_verified = 40`, `leakage_violations = 0`. |

---

## 3. Test Suite & Verification Results

- **Unit Test Discovery**: `courier/tests/test_*.py`
- **Total Test Cases Executed**: **360 tests**
- **Passed**: **360 / 360 (100%)**
- **Failed**: **0**
- **Errors**: **0**
- **Execution Time**: **79.4s**
- **Standalone Self-Test**: `courier/SELF_TEST.py` verified across 6 core subsystems in isolated clean rooms (exit code 0).

---

## 4. Portability & Zero-Leakage Audit Summary

1. **Zero Developer Path Leakage**:
   - Zero hardcoded local developer home paths across `courier/chief/`: **0 matches**.
   - Dynamic resolution via relative path lookups and clean environment overrides (`COURIER_WORKSPACE_ROOT`, `COURIER_DB_PATH`, `COURIER_HANDOFFS_DIR`, `COURIER_RUNTIME_DIR`).
2. **Zero Commercial Spend Invariant**:
   - `AUTONOMOUS_SPEND_LIMIT_EUR = 0.00` enforced in code, constitution, and Result Customs.
   - Zero credit card, bank, or payment API invocations.
3. **Mac Scope Strict Isolation**:
   - Mac reserved scopes (`courier/mac/`, `universux/`, `coordination/mac_to_windows`) strictly isolated and untracked.
4. **Two-Level Done Rigor**:
   - Local task completion (`company_local_step_erledigt`) certified by Result Customs before closure.
   - Global convergence (`company_gesamtaufgabe_erledigt`) reserved for multi-host cross-agent verification.

---

## 5. Artifact Inventory

- Package Archive: `dist/courier_symphony_v1.0.0-rc1.zip`
- Release Manifest: `dist/RELEASE_MANIFEST.json`
- Checksums: `dist/SHA256SUMS.txt`
- Acceptance Matrix: `dist/V1_ACCEPTANCE_MATRIX.json`
- Operational Recovery Card: `V1_RECOVERY_CARD.md`
- User Documentation: `README.md`
