# Courier Work Index — 2026-09-26

Purpose: one durable entry point for the current Courier work so new chats/agents do not restart analysis.

## Read first

1. `docs/COURIER_CURRENT_CONVERGENCE_CHECKPOINT_2026-09-26.md`
2. `docs/COURIER_CANARY_CONVERGENCE_PACKET_2026-09-26.md`
3. `docs/CODEX_MASTER_CONTEXT_2026-09-26.md`
4. `docs/COURIER_NUMBER_ONE_MASTERPLAN.md`
5. `docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md`

## Product laws / human layer

- `docs/COURIER_CONTINUOUS_OPERATION_PROMISE.md`
- `docs/COURIER_GRANDMA_TEST.md`
- `docs/COURIER_PERMISSION_AND_COMMUNICATION_RULES_2026-09-26.md`
- `docs/COURIER_FAST_TRACK_48H_MODE_2026-09-26.md`

Key laws:

- CONTINUE_BY_DEFAULT
- FEATHERLIGHT_BY_DEFAULT
- NO_EVIDENCE -> NO_PASS
- NO_PERMISSION_SPAM
- SHORTEST_TRUE_ANSWER_FIRST
- no busywork
- one writer per mutable scope

## Current critical path

`BOUND_FINAL_CANDIDATE -> CODEX_REVIEW -> MAC_BINDING/PREFLIGHT -> PHYSICAL A->VERIFY->B -> RESTART/NO-REPLAY`

Then, and only then, scale.

## AI queues / fleet

- `ops/ai/GOOGLE_DUAL_HOST_QUEUE_50_2026-09-26.md`
- `ops/ai/MUSE_WINDOWS_FLEET_PROMPTS_2026-09-26.md`
- `ops/ai/MUSE_VALUE_RESERVE_2026-09-26.json`
- `ops/ai/MUSE_45_LONGRUN_PROMPT.md`
- `ops/ai/VACATION_MODE_TASK_SEED_2026-09-26.json`
- `ops/ai/NUMBER_ONE_TASK_SEED_2026-09-26.json`
- `ops/ai/CONVERGENCE_REVIEW_ORDER_2026-09-26.json`
- `ops/ai/COURIER_CURRENT_CONVERGENCE_CHECKPOINT_2026-09-26.json`
- `ops/ai/GRANDMA_TEST_POLICY_2026-09-26.json`
- `ops/ai/CODEX_MASTER_CONTEXT_2026-09-26.json`

## Evidence branches prepared

- `evidence/muse-windows-20260926`
- `evidence/muse-mac-20260926`
- `evidence/google-windows-20260926`
- `evidence/google-mac-20260926`

Windows Muse evidence protocol:

- `ops/evidence/MUSE_WINDOWS_FLEET_PROTOCOL_2026-09-26.md` on `evidence/muse-windows-20260926`

## Current candidate rule

Expected minimal writer scope:

`FINAL_MINIMAL_DELTA=B`

No physical Canary is accepted until the exact candidate branch/SHA/runtime binding is known.

## Current Canary rules

RUN 1:
real A -> deterministic verify -> reconcile -> B automatic, HUMAN_RELAY=0.

RUN 2:
verifier off until A RESULT_RECEIVED -> snapshot -> controlled restart -> verifier on -> A reconciles without re-execution -> B continues.

A FAILED during Canary is an abort condition while execution-retry side-effect safety remains unresolved.

## Resume rule

A new session should:

1. read this index;
2. read the current convergence packet;
3. read fresh evidence branches/reports;
4. resume from the first unresolved causal blocker;
5. never restart unchanged proven work merely because the chat/model changed.
