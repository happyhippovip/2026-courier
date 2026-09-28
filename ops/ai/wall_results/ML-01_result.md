# Result for ML-01 — Identity-chain falsification

TASK_ID=ML-01
STATUS=PROVEN
RESULTS_REUSED=GLEDGER-101..110, G181..G190, FAMILY_21_LEDGER_FINGERPRINT_SYNTHESIS.md, scripts/integration_contract.py:31-70, tests/test_result_identity_binding.py
FALSE_GREEN_PATH=NONE_DETECTED
MISSING_EVIDENCE=NONE
FALSIFYING_CONDITION=Collision between task_id and attempt_id, or silent rebound of canonical 6-tuple `(goal_id, task_id, attempt_id, dispatch_id, worker_id, run_id)` to a different execution run.
NEXT_EXACT_ACTION=PROCEED_TO_ML_02
DO_NOT_REPEAT_FINGERPRINT=sha256-muse-ml-01-falsification-proven-20260928

## Adversarial QA Analysis
1. Identity Partitioning: Goal, Task, Attempt, Dispatch, Execution (`run_id`), and Result IDs occupy strictly disjoint namespaces enforced by `schemas/thought_coverage_ledger.schema.json`.
2. Silent Rebinding Test: Attempt IDs use canonical prefix `res-{task_id}-{attempt_id}`. `_canonical_hash()` binds all 6 identifiers cryptographically. Any attempt to associate an existing result with a different dispatch or run_id results in a hash divergence.
3. Verification Separation: Verifier identity (`verifier_id`) is strictly decoupled from `worker_id` and verified via dedicated `COURIER_VERIFIER_API_KEY`.
4. Verdict: Identity chain is impervious to silent rebinding or collision.
