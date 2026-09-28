# Family 8: Proof Card & Core Freeze Preparation

**Status**: READY FOR FREEZE VALIDATION  
**Product Reference**: `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md` (Gate 1–4 Freeze)

---

## 1. Canonical Proof Card Schema Template

```json
{
  "$schema": "https://courier.symphony/schema/v1/proof-card.json",
  "proof_card_id": "pc-2026-09-27-core-freeze",
  "goal_id": "goal-canonical-canary",
  "goal_contract_fingerprint": "sha256:d8e8f8...canonical_goal_spec",
  "task_sequence": [
    {
      "task_id": "task-a",
      "attempt_id": "task-a:attempt:1",
      "dispatch_id": "dispatch-d460fe7b11854be0941bf2a62c3b7110",
      "execution_id": "exec-mac-worker-01",
      "result_id": "result-89828ee566fc9dd853bd3fffd65f9bd4b834d56b6e5a70fcc62c99dfc1bce07b",
      "evidence_ids": [
        "art-32339451dabe1c71bcbb9b9dde4debbaacab94b411e31058987b053ae76329ea"
      ],
      "acceptance_criteria": [
        "server_bytes_match_hash",
        "independent_verifier_pass",
        "attempts_equals_one"
      ]
    },
    {
      "task_id": "task-b",
      "attempt_id": "task-b:attempt:1",
      "dispatch_id": "dispatch-cb0456bc32d0a27cb0e083d4418d1219",
      "execution_id": "exec-mac-worker-01",
      "result_id": "result-8ce1105ea18f216be82958600d2c67366c73f279409059f1a6a60c503a910615",
      "evidence_ids": [
        "art-cb0456bc32d0a27cb0e083d4418d12191a79434925f9b4980717c7bc687c72a1"
      ],
      "acceptance_criteria": [
        "auto_dispatched_after_task_a_reconciled",
        "zero_human_relay",
        "verifier_pass"
      ]
    }
  ],
  "source_fingerprint": "git:4c1e24ccc522042af826bc4c2b595daf85d097f9",
  "runtime_fingerprint": "darwin-25.6.0-x86_64-python-3.9.13",
  "covered_surface": [
    "server/app.py",
    "scripts/courier_verifier.py",
    "scripts/integration_contract.py",
    "scripts/artifact_store.py",
    "scripts/mac_worker/daemon.py"
  ],
  "unknowns": 0,
  "human_interventions": 0,
  "revalidation_status": "VALID",
  "proof_level": "LEVEL_3_CRYPTOGRAPHIC_RECONCILIATION",
  "autonomy_grade": "A4_RECOVERY_RESILIENT"
}
```

---

## 2. Core Freeze Criteria Checklist

| Criterion | Target Status | Current Evidence | Remaining Gap |
|---|:---:|---|---|
| **LEDGER_PASS** | PASS | 118 ledger entries reconciled in `ops/ai/wall_ledger/ledger.jsonl`. | Zero open schema conflicts. |
| **LEDGER_FROZEN** | FROZEN | Specification locked in `EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md`. | Pending final Windows CW 5-file patch. |
| **MOTOR_PASS** | PASS | Port 8081 Canary verified in `PHYS-002`. | Awaiting FINAL_SHA regression check. |
| **A3_ZERO_RELAY** | PASS | Proven in `PHYS-002` Canary run (`HUMAN_RELAY_COUNT=0`). | None. |
| **A4_RECOVERY_RESILIENT** | PASS | Proven in `PHYS-003` Restart Gate (zero A replay, attempts == 1). | None. |
| **BOUNDED_RESOURCES** | PASS | Guarded by `MAX_HEAVY_JOBS=1`, memory backoff, 300s stale quarantine. | None. |
| **NO_TIGHT_POLLING** | PASS | Backoff loop verified; 5s poller interval; no busy spins. | None. |
| **PROOF_CARDS_COMPLETE**| PASS | Schema instantiated; Canary proofs attested. | None. |

---

## 3. What Remains to Core Freeze
1. Windows Antigravity Central Writer applies the 3 P0 fixes across the 5 authorized files.
2. Single Codex code-grounded review confirms zero architectural drift.
3. Lock commit with `CORE_FROZEN=YES`.
