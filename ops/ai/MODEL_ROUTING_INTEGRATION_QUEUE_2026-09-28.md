# Model Routing Integration Queue — 2026-09-28

Status: READY / COORDINATION HARDENING
Purpose: make model-aware routing enforceable across every active Wall worker, not just policy text.

Canonical inputs:
- ops/ai/COURIER_MODEL_CAPABILITY_REGISTRY_2026-09-28.md
- ops/ai/WORKER_SELF_IDENTIFICATION_AND_ROUTING_CONTRACT_2026-09-28.md
- ops/ai/MODEL_AWARE_WALL_ROUTING_POLICY_2026-09-28.md
- ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md
- ops/ai/WALL_TASK_PACKET_SCHEMA.md
- ops/ai/WALL_QUEUE_CURRENT.md

Scope: coordination/prompt/task-schema only.
No application source edits.

## MR001 — Active prompt inventory
Inputs: WALL_QUEUE_CURRENT + referenced active prompt files only.
Done: list active prompts that already obey model-aware routing and those still missing it.

## MR002 — Universal wall integration
Inputs: UNIVERSAL_MD_WALL_MASTER_PROMPT.txt + routing policy.
Done: SELF_ID -> CHEAP_ROUTE -> FIT -> CLAIM -> EXECUTE -> HANDOFF order is explicit.

## MR003 — Google Windows integration
Inputs: current Windows 100X, morning, ledger, test, contradiction prompts.
Done: each reads routing policy or delegates to canonical router; no duplicate gate review.

## MR004 — Google Mac integration
Inputs: current Mac 100X, morning, run-prep, restart, core-freeze prompts.
Done: each reads routing policy and emits ROUTE_REQUIRED when wrong fit.

## MR005 — Muse integration
Inputs: Muse carryover, 0200, longrun, preflight prompts.
Done: Muse defaults to C2 independent review; LOW-value deterministic work routes away to C0/C1.

## MR006 — Codex integration
Inputs: Codex gate docs/current handoff contract.
Done: Codex is C3 only, HIGH only on a fixed durable candidate fingerprint, one reviewer per invalidation cycle.

## MR007 — Opus integration
Inputs: OPUS46 queue/worker + registry.
Done: Opus C4 tasks require explicit convergence justification and bounded admission.

## MR008 — Antigravity writer/runner integration
Inputs: master control + orchestration policy.
Done: C5 authority is explicit and cannot be self-granted by another model.

## MR009 — Reasoning-setting normalization
Inputs: all active provider prompts from MR001.
Done: every prompt says minimum sufficient level: NONE/LOW/NORMAL/MEDIUM/HIGH and never defaults to HIGH without task-class justification.

## MR010 — Window-count/admission integration
Inputs: device admission + routing policy.
Done: window recommendation derives from independent READY tasks + host motors + cost cap, not free window count.

## MR011 — Result handoff integration
Inputs: task schema + returned-result policy.
Done: every result supports:
NEXT_TASK_CLASS
NEXT_PREFERRED_PROVIDER
NEXT_PREFERRED_HOST
NEXT_REASONING_LEVEL
NEXT_WINDOW_COUNT
NEXT_PROMPT_REF

## MR012 — Unknown/future model onboarding
Inputs: capability registry + self-ID contract.
Done: unknown models start conservative C1 read-only, self-report tools/version/mode, execute one bounded representative task, and cannot self-grant write/physical authority.

## MR013 — Automatic route explanation
Inputs: router prompt + operator protocol.
Done: wrong-fit worker emits exactly:
ROUTE_REQUIRED=YES
WHERE=
PROVIDER=
MODEL_CLASS=
SETTING=
WINDOWS=
TASK=
WHY=
PROMPT_REF=

## MR014 — Cost regression guard
Inputs: cost-safe gate policy + routing policy.
Done: repeated same-fingerprint model admission is detected as duplicate/no-op and refused.

## MR015 — Routing acceptance matrix
Done when all pass:
1 deterministic task routes C0
2 bulk task routes C1
3 independent QA routes C2
4 fixed code gate routes C3
5 convergence judgment routes C4
6 final source write routes exact C5 writer
7 physical proof routes exact C5 runner
8 unknown provider stays conservative
9 expensive model not admitted for C0/C1
10 duplicate fingerprint not re-run
11 wrong-fit worker recommends exact route
12 window count is bounded by independent work/resource/cost

## MR016 — Final router handoff
Inputs: MR001..MR015 result summaries only.
Output:
ROUTER_READY=
PROMPTS_MIGRATED=
PROVIDERS_COVERED=
SETTINGS_COVERED=
AUTHORITY_GAPS=
COST_GAPS=
ACCEPTANCE_MATRIX=
OPEN=
NEXT_EXACT_ACTION=

End:
Do not invent MR017.
If all integration work is complete, TRUE_IDLE.
