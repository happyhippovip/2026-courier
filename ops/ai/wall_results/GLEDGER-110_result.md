# GLEDGER-110 Result — Reconciliation Record

TASK_ID=GLEDGER-110
STATUS=PROVEN (by reused harvested evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=L3 (transition map, 409 set, retry/quarantine rules); GLEDGER-107 (equivalence outcomes consumed); GLEDGER-109 (valid PASS input); P6 (step-index advancement); PHYS-002/003 (RECONCILED observed; attempts==1 preserved)

## Deterministic transition (normative)
Input state RESULT_RECEIVED + valid verification record →
- verdict PASS → RECONCILED. Ledger effects, atomically: task.status=RECONCILED; goal.current_step_index += 1; goal DONE iff plan exhausted; result generation sealed (further identical submits → ACK_DUPLICATE; anything else → 409 set).
- verdict FAIL → FAILED_VERIFICATION. Task parked retryable (resume mints attempt n+1). A FAILED execution never converts to PASS on any path (no retry-into-PASS, no FAIL→RECONCILED edge exists).
- Void verification (failing GLEDGER-109 validity) → no transition; task stays RESULT_RECEIVED.
Duplicate submit on already-RECONCILED: equivalent → ACK (no ledger effect); non-equivalent → 409 (no ledger effect). Reconciliation is idempotent under replay and closed under contradiction (latter → GLEDGER-115, never ACK).

## Ledger effects (normative outcome fields)
Reconciliation record: {task_id, result_id, generation (attempt, dispatch_id), verdict, verifier_id, reconciled_at, goal_id, step_index_before, step_index_after, goal_status_after}. Every effect above derives from these fields; no side channels (no wall-clock-only decisions, no unpublished state).

## Failure-terminal edge
FAILED_TERMINAL is entered only via explicit terminal-failure handling (not via FAIL verdict alone, which parks retryable). From FAILED_TERMINAL, the ONLY exit is resume→new attempt; no direct path to RECONCILED exists for any prior generation.

MISSING=None for transition/effects definition.
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-111 (NEXT_READY reads step_index_after + goal_status_after); GLEDGER-115 (contradiction input); GLEDGER-128 (harvester encodes this transition).
DO_NOT_REPEAT_FINGERPRINT=gledger-110-reconciliation-record-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-f0d3b6eedc2ae9d0

DO_NOT_REPEAT_FINGERPRINT=sha256-4fbda5a00618965b

DO_NOT_REPEAT_FINGERPRINT=sha256-dbf2ea1e0609bc3a
