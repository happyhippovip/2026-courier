# GLEDGER-103 Result — Canonical Task Record

TASK_ID=GLEDGER-103
STATUS=PROVEN (by reused harvested evidence; no new source reads)
HOST=MAC
PROVIDER=GOOGLE
INPUTS_READ=ops/ai/LEDGER_FINISH_QUEUE_30_2026-09-27.md (definition only)
RESULTS_REUSED=GLEDGER-101 (chain/ownership); GLEDGER-102 (prepare_task defaults, TASK_STATES, capability map); POST200-021 (binding enforcement); PHYS-002 (task lifecycle observed: QUEUED→DISPATCHED→RESULT_RECEIVED→RECONCILED)

## Canonical Task record
REQUIRED: `task_id` (`task-<slug>-<hash4>`, unique per goal), `goal_id` (parent link), `target_capability` (github|mac|windows|linux — sole dispatch-routing key, mapped to canonical worker_id at prepare), `worker_id` (server-assigned at dispatch, never worker-chosen), `attempt` (integer ≥1, server-incremented only via resume), `dispatch_id` (fresh per claim), `status` ∈ TASK_STATES, `artifacts` (task-owned expectation list: names, or dicts {path, expected_sha256} per task template — the ONLY trusted-expectation source), `result` (null until RESULT_RECEIVED; then the bound DurableResult).
OPTIONAL: `run_id`, `result_id` (null until bound), human-readable labels, creation/progress timestamps.
FORBIDDEN: worker-set worker_id/attempt/dispatch_id; execution content; worker-originated expected hashes; second identity aliases.

## Dependencies
Inter-task ordering is positional, not linked-list: a task is eligible iff it is `workflow_plan[current_step_index]` of a non-BLOCKED goal (GLEDGER-101 §11). No per-task depends_on edges exist in the observed contract — sequential index gating IS the dependency mechanism. Consequence for Ledger: record `goal_id + plan_index` as the dependency coordinate; do not invent `depends_on`/`blocks` fields.

## Acceptance (per-task)
A task is accepted (RECONCILED) iff: result submitted with full identity binding (GLEDGER-102 verify_result rule) + artifact refs pass `check_reference` against server records + independent verifier posts PASS with identical artifacts. FAIL verdict → FAILED_VERIFICATION (retryable) — never silently converted. Missing task artifacts expectation → legacy record-binding path only, never exact-content PASS (POST200-021 case 6).

## Owner scope
Writer: server dispatch path (creates/binds/dispatches). Mutators: worker (result submit only), independent verifier (verdict only), resume path (attempt increment only from terminal/human-required states). Readers: all (claim polls, expiry sweeps, harvesters). No other writer exists — any Ledger write outside these four paths is an ownership violation.

MISSING=None for the record definition. Open item carried forward (not this task): server-path result_id canonicalization (GLEDGER-107).
BLOCKER=None in-lane.
NEXT_DEPENDENCY=GLEDGER-104 (attempt/dispatch identity builds on attempt+dispatch_id rules above).
DO_NOT_REPEAT_FINGERPRINT=gledger-103-task-record-complete

DO_NOT_REPEAT_FINGERPRINT=sha256-e585771dac9902d9

DO_NOT_REPEAT_FINGERPRINT=sha256-8e50f01ec255214a

DO_NOT_REPEAT_FINGERPRINT=sha256-cb3a18ba32a30e7d
