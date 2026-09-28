# Result for MPREP-06: Proof-Card Missing Fields

TASK=MPREP-06
STATUS=PASS
RESULTS_REUSED=ops/ai/coordination_reports/FAMILY_08_PROOF_CARD_CORE_FREEZE.md, ops/ai/wall_v2/publish_queue/PHYSICAL_CANARY_PROOF_BUNDLE_2026-09-27.md
OUTPUT=Proof Card Fields Audit (Required vs Unknown):
- `proof_card_id`: `PRESENT` (`pc-2026-09-27-core-freeze`)
- `goal_id`: `PRESENT` (`goal-canonical-canary`)
- `goal_contract_fingerprint`: `PRESENT` (`sha256:d8e8f8...canonical_goal_spec`)
- `task_sequence[].task_id`: `PRESENT` (`task-a`, `task-b`)
- `task_sequence[].attempt_id`: `PRESENT` (`attempts == 1`)
- `task_sequence[].dispatch_id`: `PRESENT` (`dispatch-d460fe7b...`, `dispatch-cb0456bc...`)
- `task_sequence[].execution_id`: `PRESENT` (`exec-mac-worker-01`)
- `task_sequence[].result_id`: `PRESENT` (verified hashes on Port 8081)
- `task_sequence[].evidence_ids`: `PRESENT` (`art-32339451...`, `art-cb0456bc...`)
- `task_sequence[].acceptance_criteria`: `PRESENT` (12-case matrix mappings)
- `source_fingerprint`: **UNKNOWN** (Currently pinned to base `4c1e24cc`; final candidate SHA pending Windows Central Writer)
- `runtime_fingerprint`: `PRESENT` (`darwin-25.6.0-x86_64-python-3.9.13`)
- `covered_surface`: `PRESENT` (5 core files)
- `unknowns`: `PRESENT` (0)
- `human_interventions`: `PRESENT` (0)
- `revalidation_status`: `PRESENT` (`VALID`)
- `proof_level`: `PRESENT` (`LEVEL_3_CRYPTOGRAPHIC_RECONCILIATION`)
- `autonomy_grade`: `PRESENT` (`A4_RECOVERY_RESILIENT`)

**Unknown Fields Only**:
1. `source_fingerprint`: Value remains `UNKNOWN` until Windows Central Writer emits `FINAL_SHA`.
MISSING=Publication of `FINAL_SHA` from Windows.
BLOCKER=Windows Central Writer commit.
MUSE_INPUT=Muse 02:00 must verify that upon FINAL_SHA publication, `source_fingerprint` in the proof card is updated and bound.
DO_NOT_REPEAT_FINGERPRINT=mprep-06-proof-card-missing-fields-v1

DO_NOT_REPEAT_FINGERPRINT=sha256-716b9423555ad25f
