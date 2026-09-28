# GLEDGER-102 Result — Goal/Contract Minimum Fields

TASK_ID=GLEDGER-102
STATUS=PROVEN (field names from candidate-b-1 `scripts/integration_contract.py` + server goal behavior; goal-intake exact schema flagged, see MISSING)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition); origin/candidate-b-1:scripts/integration_contract.py lines 1–70 (exact names only, per queue allowance); reused GLEDGER-101 entity chain + proof-bundle goal behavior
RESULTS_REUSED=GLEDGER-101 (chain root); POST200-021; PHYS-002 (goal-d0a02c0e lifecycle)

## GOAL — minimum fields
REQUIRED: `goal_id` (string, `goal-<hash8>`), `workflow_plan` (ordered list; each step addressable by index; step carries task template incl. `task_id`, `target_capability`, `artifacts` expectation), `status` (QUEUED/BLOCKED/DONE observed), `current_step_index` (integer, starts 0, +1 only on PASS verify).
OPTIONAL: goal metadata (human-readable name, creation timestamp, owner scope).
FORBIDDEN: worker-supplied execution content; expected hashes originating from any worker (trusted-content rule — expectations enter only via workflow_plan/task template).
Observed duality to preserve: local build path derives `attempt_id` as `{task_id}:attempt:1` string (prepare_task), server path uses integer `attempt` + `dispatch-<uuidhex12>`; both bind the same logical attempt — canonical Ledger records integer attempt + dispatch_id, local attempt_id string is a transport alias, not a second identity.

## CONTRACT — minimum fields (rules, not a stored record)
REQUIRED constants: TASK_STATES = {QUEUED, DISPATCHED, RESULT_RECEIVED, RECONCILED, FAILED_VERIFICATION, FAILED_TERMINAL, HUMAN_REQUIRED}; RESULT_STATES = {SUCCESS, FAILED}; capability→worker map ({github, mac, windows, linux} → canonical worker IDs); canonical-hash function (sha256 over sort_keys compact JSON) for result_id derivation on local path.
REQUIRED behaviors: prepare_task defaults (attempt/dispatch/worker binding, status QUEUED, status-membership check); verify_result identity binding (goal_id/task_id/attempt/dispatch/worker must all match dispatched task); ContractError (a ValueError) as the single rejection type for unbindable envelopes.
FORBIDDEN in contract: silent defaults that change identity (no default result_id on server path); worker-overridable worker_id; any PASS without evidence (GLEDGER-109 dependency noted).

MISSING=Server goal-intake exact required schema (goal creation endpoint fields beyond observed goal_id/workflow_plan/status/current_step_index); normative task for a later gap-map (GLEDGER-125/126 may cover).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-103 (Task record), GLEDGER-109 (verification record uses RESULT_STATES + no-evidence-no-PASS rule above).
DO_NOT_REPEAT_FINGERPRINT=gledger-102-goal-contract-fields-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-4df38952c48082bd

DO_NOT_REPEAT_FINGERPRINT=sha256-890abeefabaddc78

DO_NOT_REPEAT_FINGERPRINT=sha256-8745971786b55708
