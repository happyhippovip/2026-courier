# Family 8: Core Freeze Evidence Map & Proof Card Specification

Status: COMPLETE
Purpose: Cryptographic and operational evidence schema required to declare CORE_FREEZE.

---

## 1. Proof Card Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CourierCoreFreezeProofCard",
  "type": "object",
  "required": [
    "goal_id",
    "goal_contract_fingerprint",
    "task_id",
    "attempt_id",
    "execution_id",
    "result_id",
    "evidence_ids",
    "acceptance_criteria",
    "source_fingerprint",
    "runtime_fingerprint",
    "covered_surface",
    "unknowns",
    "human_interventions",
    "revalidation_status",
    "proof_level",
    "autonomy_grade"
  ],
  "properties": {
    "goal_id": { "type": "string" },
    "goal_contract_fingerprint": { "type": "string" },
    "task_id": { "type": "string" },
    "attempt_id": { "type": "string" },
    "execution_id": { "type": "string" },
    "result_id": { "type": "string" },
    "evidence_ids": { "type": "array", "items": { "type": "string" } },
    "acceptance_criteria": { "type": "array", "items": { "type": "string" } },
    "source_fingerprint": { "type": "string" },
    "runtime_fingerprint": { "type": "string" },
    "covered_surface": { "type": "string" },
    "unknowns": { "type": "array", "items": { "type": "string" } },
    "human_interventions": { "type": "integer" },
    "revalidation_status": { "type": "string", "enum": ["VALID", "REVALIDATION_REQUIRED", "STALE"] },
    "proof_level": { "type": "string", "enum": ["L0_CLAIMS_ONLY", "L1_SYNTAX_ONLY", "L2_TARGETED_MOCKS", "L3_INTEGRATED_TESTS", "L4_PHYSICAL_PROOF"] },
    "autonomy_grade": { "type": "string", "enum": ["A1_ASSISTED", "A2_SUPERVISED", "A3_ZERO_RELAY", "A4_RECOVERY_RESILIENT"] }
  }
}
```

---

## 2. Core Freeze Requirements Gap Analysis

| Milestone | Target Requirement | Current State | Remaining Gap |
|---|---|---|---|
| **LEDGER_FROZEN** | Schema locked, all 14 identity fields enforced, duplicate matching on 5-tuple | Specification complete (`EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md`) | Central Writer code patch for 5-tuple duplicate check in `server/app.py` |
| **MOTOR_PASS** | Precheck admission, rate-limiting, and timeout kill verified | Motor eligibility v1 verified, timeout kill verified | Staged in `origin/coordination` |
| **A3_ZERO_RELAY** | Automatic task transition from Step A to Step B with zero human relay | Physical proof completed on Port 8081 (`run1_proof.json`) | Re-execute against final candidate SHA |
| **A4_RECOVERY_RESILIENT** | State survives crash/restart; attempts count strictly preserved (`attempts == 1`) | Physical proof completed on Port 8081 (`run2_proof.json`) | Re-execute against final candidate SHA |
| **CORE_FREEZE** | All 4 gates green, 0 blockers, 0 diff-check errors | Blocked on Phase 1 Central Writer commit | Central Writer patch -> Codex review -> Final Physical Proof |
