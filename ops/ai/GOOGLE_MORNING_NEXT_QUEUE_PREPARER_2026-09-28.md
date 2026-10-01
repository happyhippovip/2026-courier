# Google Morning Next-Queue Preparer — 2026-09-28

Status: MORNING GENERATOR / ONE PREPARER ONLY

Purpose:
Generate the next real Google work generation after G181..G280 and current Mac support queues finish, using only durable overnight results, explicit Windows Central Writer handoff, current gate state, and open causal blockers.

## Inputs

Read only:
- ops/ai/WALL_SYSTEM.md
- ops/ai/WALL_QUEUE_CURRENT.md
- ops/ai/COURIER_MASTER_CONTROL_PLANE_2026-09-27.md
- ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md
- current queue result summaries
- current Central Writer handoff
- current RUN_1/RUN_2/Core-Freeze evidence summaries

Do not broad-scan source.

## Generation rule

Create a next generation only from real unresolved items in this order:

1. FINAL_SHA / exact five-file / targeted-test / 12-case evidence gaps
2. Ledger persistence / replay / trusted-content / reconcile / NEXT_READY gaps proven by prior queue results
3. exact missing targeted tests or deterministic checks
4. RUN_1 preflight gaps
5. RUN_2/restart gaps
6. Proof Card / Core Freeze gaps
7. Wall cost/resource/continuity gaps
8. bounded pilot-prep gaps only when higher priorities have no READY work

Do NOT create:
- speculative architecture
- duplicate reviews
- another WBUILD sequence
- arbitrary G281+ merely because capacity exists
- work already closed by durable evidence

## Host routing

WINDOWS preferred:
- candidate-sensitive deterministic verification
- narrow source/test inspection
- exact targeted pytest
- Ledger/server/integration gap verification
- Pre-Codex evidence

MAC preferred:
- RUN_1/RUN_2 preparation
- restart matrix
- cross-host/runtime binding
- Proof Cards/Core Freeze
- Muse preflight
- resource-safe physical-proof preparation

Either host:
- result harvesting
- synthesis
- cost/resource review
- continuity evidence
- pilot-prep docs

## Output

Write one durable queue generation with:
TASK_ID
HOST_PREFERENCE
PRIORITY
DEPENDENCIES
EXACT_INPUTS
ALLOWED_ACTION
ALLOWED_TEST
DONE_CONDITION
RETEST_TRIGGER
DO_NOT_REPEAT_FINGERPRINT

Also write:
GENERATION_ID=
CREATED_FROM_RESULT_FINGERPRINTS=
FINAL_SHA_STATE=
PRE_CODEX_STATE=
RUN1_STATE=
RUN2_STATE=
CORE_FREEZE_STATE=
TASK_COUNT=
TRUE_IDLE_IF_ZERO=

If no real tasks exist:
TASK_COUNT=0
TRUE_IDLE=YES
and do not invent filler.
