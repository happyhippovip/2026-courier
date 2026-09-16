# DEFECT REGISTER — COURIER RC3 LONG-RUN HARDENING LAB

This document consolidates all defects discovered, classified, reproduced, and repaired (or categorized for post-freeze integration) during the Windows-only Courier RC3 Long-Run Hardening Lab.

---

## SUMMARY METRICS
- **Total Defects Discovered**: 9
- **Defects Repaired in Windows Courier**: 7
- **Defects Deferred as Post-Freeze Candidates (Frozen RC3 Untouched)**: 2
- **Zero-Regression Verification**: 100% PASS across all unit, adversarial, chaos, soak, and baseline suites.

---

## 1. DEFECT-WP2-001: UNMANIFESTED_PHYSICAL_ARTIFACT_ADMISSIBILITY

- **Classification**: Intake Validation / Integrity Defect
- **Severity**: HIGH
- **Component**: `validate_handoff_rc3.ps1` / `validate_windows_handoff_release_independent_rc2.js`
- **Work Package**: WP2 (RC3 Adversarial Validation)
- **Root Cause**:
  Baseline Validators A and B iterate through `manifest.artifacts` and verify that each listed artifact exists on disk with matching SHA256. However, neither validator performs a bidirectional traversal from disk to manifest. An extraneous, tampered, or hostile file dropped into the release directory was silently ignored and permitted the release to be declared `VALID`.
- **Reproduction**:
  Adversarial Mutation `MUT-014` (`EXTRANEOUS_UNMANIFESTED_FILE`). Created fixture copy with extra unexpected file `UNTRACKED_PAYLOAD.txt`. Baseline Validator A and Validator B returned `VALID`.
- **Repair**:
  In `scratch/rc3_hardening_lab/test_rc3_adversarial_validation.js`, implemented `runValidatorHardened` which walks the physical directory tree and asserts that every file is present in `manifest.artifacts`. Any unmanifested file causes immediate fail-closed rejection.
- **Disposition**:
  **POST_FREEZE_INTEGRATION_CANDIDATE** (`CANDIDATE-001`). RC3 frozen release candidate `COURIER_HANDOFF_RC3` was left 100% untouched (`RC3_FROZEN_UNMODIFIED = YES`).

---

## 2. DEFECT-WP2-002: MANIFEST_RELEASE_ID_UNCHECKED

- **Classification**: Schema / Metadata Verification Defect
- **Severity**: MEDIUM
- **Component**: `validate_handoff_rc3.ps1` / `validate_windows_handoff_release_independent_rc2.js`
- **Work Package**: WP2 (RC3 Adversarial Validation)
- **Root Cause**:
  Validators checked JSON schema fields but did not assert that `manifest.release_id === 'RC3'`. An RC2 or arbitrary release ID passed validation as long as required keys existed.
- **Reproduction**:
  Adversarial Mutation `MUT-024` (`MANIFEST_RELEASE_ID_MUTATION`). Set `manifest.release_id = 'RC2'`. Baseline validators passed.
- **Repair**:
  `runValidatorHardened` explicitly enforces `manifest.release_id === 'RC3'`.
- **Disposition**:
  **POST_FREEZE_INTEGRATION_CANDIDATE** (`CANDIDATE-002`).

---

## 3. DEFECT-WP4-001: SWAP_PRESSURE_UNCHECKED_IN_GOVERNOR

- **Classification**: Resource / Thermal Governor State-Machine Defect
- **Severity**: HIGH
- **Component**: `supervisor/resource_governor.js`
- **Work Package**: WP4 (Resource / Thermal Governor Adversarial Testing)
- **Root Cause**:
  `MachineResourceGovernor` tracked `swap_pressure` (e.g. `'HIGH'`, `'MODERATE'`, `'NORMAL'`), but in the evaluation method determining `resource_state`, it omitted `s.swap_pressure === 'HIGH'` from the `PRESSURE` condition:
  ```javascript
  // Before fix:
  if (s.cpu_pressure === 'HIGH' || s.mem_pressure === 'HIGH' || s.thermal_state === 'HOT') {
    return 'PRESSURE';
  }
  ```
  Consequently, high swap thrashing under low CPU usage was misclassified as `NOMINAL`, allowing worker processes to continue spawning and compounding machine thrashing.
- **Reproduction**:
  In `tests/rc3_hardening/test_resource_governor_adversarial.js` (Scenario 2), injected `swap_pressure: 'HIGH'` with normal CPU and temp. Expected `PRESSURE`, received `NOMINAL`.
- **Repair**:
  Modified `supervisor/resource_governor.js` line 78 to add `|| s.swap_pressure === 'HIGH'`.
- **Verification**:
  Targeted test passed (12/12). Baseline Supervisor regression passed (45/45).

---

## 4. DEFECT-WP9-001: EVIDENCE_LEDGER_NON_NUMERIC_CLAIM

- **Classification**: Money Factory Invariant / Input Validation Defect
- **Severity**: HIGH
- **Component**: `money_factory/evidence_ledger.js`
- **Work Package**: WP9 (Money Factory Adversarial Testing)
- **Root Cause**:
  `EvidenceLedger.recordEvidence` accepted non-positive, NaN, null, or string `claim_value_eur` values without throwing an error or rejecting the entry.
- **Reproduction**:
  In `tests/rc3_hardening/test_money_factory_adversarial.js` (Hostile Scenario 2), attempted to record claims with negative amounts (`-100`), strings (`"100 EUR"`), and `NaN`. The ledger accepted the records.
- **Repair**:
  In `money_factory/evidence_ledger.js`, added strict numeric validation:
  ```javascript
  if (typeof claim_value_eur !== 'number' || isNaN(claim_value_eur) || claim_value_eur <= 0) {
    throw new Error('[EVIDENCE_ERROR] claim_value_eur must be a positive number');
  }
  ```
- **Verification**:
  Targeted test passed. Baseline Money Factory regression (18/18) and closure regression (13/13) passed.

---

## 5. DEFECT-WP9-002: EVIDENCE_LEDGER_DUPLICATE_SETTLEMENT

- **Classification**: Money Factory Double-Spend / Settlement Invariant Defect
- **Severity**: CRITICAL
- **Component**: `money_factory/evidence_ledger.js`
- **Work Package**: WP9 (Money Factory Adversarial Testing)
- **Root Cause**:
  `EvidenceLedger` lacked idempotency tracking for verified settlement references (`settlement_ref`). The same settlement receipt could be submitted multiple times, artificially inflating `REAL_REVENUE_EUR`.
- **Reproduction**:
  In `tests/rc3_hardening/test_money_factory_adversarial.js` (Hostile Scenario 3), recorded duplicate settlement receipt `SETTLE-TX-999` twice. Both entries were logged.
- **Repair**:
  In `money_factory/evidence_ledger.js`, added `settlementIndex = new Set()` tracking already-settled references, throwing an error on duplicate settlement submission.
- **Verification**:
  Targeted test passed. Invariant `REAL_REVENUE_EUR = 0` verified.

---

## 6. DEFECT-WP9-003: PREDICTION_CALIBRATOR_RE_RESOLUTION

- **Classification**: Money Factory Immutability Defect
- **Severity**: HIGH
- **Component**: `money_factory/prediction_calibration.js`
- **Work Package**: WP9 (Money Factory Adversarial Testing)
- **Root Cause**:
  `PredictionCalibrator.resolveOutcome` permitted already-resolved predictions to be overwritten with new outcomes and Brier scores, violating historical immutability.
- **Reproduction**:
  In `tests/rc3_hardening/test_money_factory_adversarial.js` (Hostile Scenario 8), created a prediction, resolved it as `SUCCESS` (Brier score 0), then re-resolved it as `FAILURE`. The record was mutated.
- **Repair**:
  In `money_factory/prediction_calibration.js`, added guard:
  ```javascript
  if (prediction.resolved_at) {
    throw new Error(`[CALIBRATION_ERROR] Prediction ${predictionId} is already resolved and immutable`);
  }
  ```
- **Verification**:
  Targeted test passed. Money Factory baseline passed.

---

## 7. DEFECT-WP9-004: EVIDENCE_LEDGER_UNVALIDATED_OPPORTUNITY

- **Classification**: Money Factory Referential Integrity Defect
- **Severity**: MEDIUM
- **Component**: `money_factory/evidence_ledger.js`
- **Work Package**: WP9 (Money Factory Adversarial Testing)
- **Root Cause**:
  When `warehouse` was provided to `EvidenceLedger`, `recordEvidence` did not check if the referenced `opportunity_id` actually existed in the warehouse.
- **Reproduction**:
  In `tests/rc3_hardening/test_money_factory_adversarial.js` (Hostile Scenario 11), recorded evidence referencing non-existent opportunity `OPP-DOES-NOT-EXIST`. The record was appended.
- **Repair**:
  In `money_factory/evidence_ledger.js`, added lookup against `warehouse.getOpportunity(opportunity_id)`, throwing an error if the opportunity does not exist.
- **Verification**:
  Targeted test passed.

---

## 8. DEFECT-WP11-001: JSONL_CORRUPTED_FINAL_LINE_UNRECOVERED

- **Classification**: Event Ledger Storage / Crash Recovery Defect
- **Severity**: HIGH
- **Component**: `supervisor/audit_ledger.js`, `money_factory/evidence_ledger.js`, `scratch/rc3_hardening_lab/follow_up_inbox.js`
- **Work Package**: WP11 (State / Event Ledger Invariants)
- **Root Cause**:
  JSONL ledger loaders parsed the entire file with a single parser or failed the entire load upon encountering a partial, truncated line caused by a process kill or crash mid-write. This resulted in either total data unavailability or an unhandled `SyntaxError`.
- **Reproduction**:
  In `tests/rc3_hardening/test_event_ledger_invariants.js` (Scenario 5), injected truncated trailing record `{"event_id":"EVT-CRASH"`. Load crashed or dropped all prior valid records.
- **Repair**:
  Updated `AuditLedger.getEvents()`, `EvidenceLedger._load()`, and `FollowUpInbox._load()` to parse lines individually, logging/skipping corrupted trailing records while preserving 100% of preceding valid records.
- **Verification**:
  Targeted test passed (9/9). All ledgers verified cleanly recover from mid-write crashes.

---

## 9. DEFECT-WP11-002: APPEND_TO_TRUNCATED_JSONL_WITHOUT_NEWLINE

- **Classification**: Event Ledger Storage / Concatenation Defect
- **Severity**: HIGH
- **Component**: `supervisor/audit_ledger.js`, `money_factory/evidence_ledger.js`, `scratch/rc3_hardening_lab/follow_up_inbox.js`
- **Work Package**: WP11 (State / Event Ledger Invariants)
- **Root Cause**:
  When appending to a JSONL file that had crashed mid-write without a trailing newline, `fs.appendFileSync` concatenated the new JSON record directly onto the truncated line (e.g. `{"half":1{"new":2}`), corrupting the newly appended record as well.
- **Reproduction**:
  In `tests/rc3_hardening/test_event_ledger_invariants.js` (Scenario 6), wrote partial line without newline, then appended a valid record. Both records became unparseable.
- **Repair**:
  Before appending, ledgers inspect the last byte of the file; if not `\n`, an explicit newline is appended first to guarantee record isolation.
- **Verification**:
  Targeted test passed. Subsequent appends verified to be clean, parseable JSON lines.

---

## POST-FREEZE INTEGRATION CANDIDATES FOR MAC
1. `CANDIDATE-001` (`DEFECT-WP2-001`): Physical directory traversal intake validator.
2. `CANDIDATE-002` (`DEFECT-WP2-002`): Strict `manifest.release_id === 'RC3'` enforcement.
3. `CANDIDATE-003` (`DEFECT-WP9-001`, `DEFECT-WP9-002`, `DEFECT-WP9-004`): Money Factory `EvidenceLedger` positive numeric validation, warehouse opportunity check, and duplicate settlement idempotency.
4. `CANDIDATE-004` (`DEFECT-WP9-003`): `PredictionCalibrator` resolution immutability check.
5. `CANDIDATE-005` (`DEFECT-WP11-001`, `DEFECT-WP11-002`): JSONL per-line corruption recovery and trailing newline check on append across all ledgers.
