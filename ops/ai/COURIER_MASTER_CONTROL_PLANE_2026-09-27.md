# COURIER MASTER CONTROL PLANE — 2026-09-27

Status: DURABLE MASTER INDEX
Branch: coordination/autofill-task-seed-20260926

Purpose: this file is the first durable entry point when chat/session context is stale or unavailable. Do not reconstruct Courier from conversation history when this repo truth exists.

## Core promise

Courier should let a user start once, return later, and see what is done, what is really verified, what is missing, what continued automatically, and why anything stopped.

External promise:
Courier brings the user back the next day exactly where they left off.

## Product laws

- CONTINUE_BY_DEFAULT
- FEATHERLIGHT_BY_DEFAULT
- THE_GRANDMA_TEST
- NO_EVIDENCE_NO_PASS
- NO_BUSYWORK
- SHORTEST_TRUE_ANSWER_FIRST
- NO_PERMISSION_SPAM
- DUAL_SURFACE_TRUTH
- SHOW_THE_MAGIC_NOT_THE_MACHINERY
- WORLD_FEELING_MUST_NOT_DELAY_CORE_PROOF

## Canonical current technical truth

LEDGER_STATUS=FROZEN
LEDGER_ROUTING=DISABLED_UNLESS_RETEST_TRIGGER

Current gate state is authoritative from:
ops/ai/GATE_STATE_CURRENT.md

Current reported final candidate:
34b0a4264bf763bc2a78f761ffba36e47706b2cf

Current gate snapshot:
PRE_CODEX_STATE=VALIDATING
REPORTED_PRE_CODEX_READY=YES
REMOTE_GITHUB_RESOLUTION=FOUND_ON_candidate-b-1
AUTHORITATIVE_READY=NO
NEXT=CLAUDE_CODEX_FIXED_CANDIDATE_CONSUME

Do not reopen Ledger work unless a concrete durable RETEST_TRIGGER exists.
Do not redo remote-durability work already proven.

Accepted repair base:
candidate-b-1
4c1e24ccc522042af826bc4c2b595daf85d097f9

Rejected:
candidate-b-2
83940de3d7d33776a712e7506aa76726d16f8587

candidate-b-3 is NOT required.

Only Windows Antigravity Central Writer owns final-candidate application source writes unless newer durable coordination explicitly changes ownership.

Exact final-candidate file scope:
- scripts/courier_verifier.py
- scripts/integration_contract.py
- tests/test_artifact_upload_flow.py
- server/app.py
- tests/test_p3_server_idempotency.py

Trusted-content rule:
expected_sha256 comes from trusted task/workflow input, never from worker-controlled result authority.

Duplicate/replay rule:
duplicate ACK only for the same canonical result in the same attempt and dispatch generation.

Any FAILED execution invalidates RUN_1. Never retry a failed run into a fake PASS.

## Required final acceptance surface

1. task-owned expected hash survives Goal -> Claim -> Pending Verification
2. correct server bytes PASS
3. wrong server bytes FAIL
4. worker expected hash rejected
5. worker omission does not bypass task expectation
6. missing task expectation remains legacy integrity only
7. malformed/ambiguous target FAIL
8. identical replay ACK, including persistence/reload where relevant
9. changed status not duplicate success
10. changed worker not duplicate success
11. changed attempt/dispatch rejected
12. changed artifact result not duplicate success

SKIPPED required tests invalidate the final handoff.

## Critical path

Current post-Ledger order:

0. Ledger FROZEN; no routing back without RETEST_TRIGGER.
1. PRE_CODEX durability/fixed-candidate validation — single owner.
2. Candidate-independent Muse/Google prep may continue in parallel, non-blocking.
3. Optional convergence only if useful; it must not block a clean gate.
4. Codex HIGH exactly once on the exact fixed candidate when AUTHORITATIVE_READY=YES.
5. Exact Mac source/build/runtime/config/evidence binding.
6. RUN_1 physical once.
7. RUN_2 restart/no-replay once.
8. Core Freeze.
9. Minimum real pilot.
10. Product Shell only after positive pilot signal.
11. Packaging/Updates after Core + pilot evidence.
12. Broader wall/connectors/Brain/community/world/shared-capability expansion only after proof.

Canonical endgame sequence:
ops/ai/CANONICAL_ENDGAME_SEQUENCE_2026-09-28.md

## Model/host roles

Windows Antigravity:
- ONLY final-candidate source writer
- smallest causal source change
- exact authorized scope only

Mac Antigravity:
- physical proof runner
- RUN_1/RUN_2 only after exact final binding and review

Google CLI:
- read-only support / targeted deterministic checks / queue work
- harvest -> execute -> prepare -> truthful idle
- no application-source mutation unless newer durable authority explicitly grants it

Muse:
- read-only finalization/reproducer/reviewer by default
- useful for wall work, ledger checks, proof preparation, result harvesting
- not routine source writer

Codex:
- preserve for one code-grounded HIGH final review after FINAL_SHA + real tests exist

Opus/Ultracode:
- preserve for meaningful final product/convergence judgment, not routine wall work

## Wall operating doctrine

Logical wall size != heavy process count.

Current default:
MAX_HEAVY_JOBS=1 per host unless newer proven resource policy changes it.

Prefer smooth verified throughput over maximum visible concurrency.

Queue work must use durable claims/results. New provider/session/account context does not reset completed work.

When no READY work:
1. harvest pending durable results
2. refresh queue once from canonical truth + result summaries + explicit writer handoff + open blockers
3. if still empty: TRUE_IDLE
4. do not broad-scan or invent work merely to keep models busy

## Context hygiene

SESSION MEMORY = CACHE
REPO + LEDGER + TASK PACKETS = DURABLE TRUTH

At every handoff / provider change / phase change / long-session end:
CHECKPOINT
-> persist proven state
-> persist exact next action
-> clear stale context or start fresh session
-> reload minimal current truth
-> continue from repo

Do not clear mid-uncheckpointed mutation.

## Sleep / overnight mode

Long unattended rounds may be up to 10 hours when resource-safe.

Use one reusable master prompt per provider/session.

Do not keep paid/API workers alive for idle analysis.
When TRUE_IDLE is proven, stop or lightweight-backoff without repeated model reads.

## Release philosophy

Do not delay first real pilot for:
- giant dashboard
- marketplace
- enterprise admin
- Kubernetes/multi-region
- perfect installer
- full billing platform
- community/world features
- millions-of-tasks scale theater

The first pilot needs trustworthy continuation, clear state, proof, next action, bounded setup, and real measurements.

## Pilot metrics

Measure at least:
- HIPG: human continuation interventions per Goal
- RSR: passed restart scenarios / defined executed restart scenarios
- NDR: next-day return
- setup time
- support effort
- provider cost
- payment yes/no where applicable

## Updates / security direction

After Core + pilot proof:
- reproducible build
- source/build/runtime identity
- single instance
- signed/safe update path
- rollback
- Last Known Good
- state compatibility
- no lost in-flight work
- daily bounded update/safety check
- crypto agility / post-quantum migration readiness
- never claim "quantum secure" without a concrete proven profile

## Durable entry points

Canonical product plan:
docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md

Current session truth:
ops/ai/COURIER_SESSION_STATE_2026-09-26.json

Returned-result policy:
ops/ai/RETURNED_RESULT_POLICY.md

Wall system:
ops/ai/WALL_SYSTEM.md

Current queue pointer:
ops/ai/WALL_QUEUE_CURRENT.md

Wall build queue:
ops/ai/WALL_BUILD_QUEUE_V1.md

Windows Google queue:
ops/ai/GOOGLE_WINDOWS_NIGHT_QUEUE_50_2026-09-27.md

Pre-Codex stop gate:
ops/ai/GOOGLE_PRE_CODEX_GATE_2026-09-27.md

Current gate state:
ops/ai/GATE_STATE_CURRENT.md

Canonical post-Ledger endgame:
ops/ai/CANONICAL_ENDGAME_SEQUENCE_2026-09-28.md

Live status:
ops/ai/LIVE_STATUS_CURRENT.md

Ledger freeze marker:
ops/ai/LEDGER_FREEZE_CURRENT.md

Permanent Google pre-Codex prompt:
ops/ai/GOOGLE_PRE_CODEX_MASTER_PROMPT.txt

Mac large pre-Codex preparation prompt:
ops/ai/MAC_PRE_CODEX_MEGA_MASTER_PROMPT.txt

Founder life/company master plan (public-safe):
docs/FOUNDER_LIFE_AND_COMPANY_MASTER_PLAN_PUBLIC_SAFE_2026-09-28.md

Context hygiene:
ops/ai/CONTEXT_HYGIENE_AND_HANDOFF_POLICY_2026-09-26.md

Overnight wall:
ops/ai/OVERNIGHT_WALL_10H_POLICY_2026-09-26.md

V1 capacity/update/crypto:
docs/V1_CAPACITY_UPDATES_AND_CRYPTO_READINESS_PLAN.md

## Privacy boundary

This repository is public.

Never persist:
- API keys
- passwords
- session secrets
- exact card/account identifiers
- private identity data
- private personal-life details not already intentionally made public

Personal/private planning that is not product-operational must live in a private store/repository, not here.

## Chief rule

When asked "what next?", start from this file + current durable state. Do not ask the human to reconstruct the plan from memory.

## Shared capability / update strategic direction

Canonical product/business strategy:
`docs/COURIER_SHARED_CAPABILITY_UPDATE_FABRIC_2026-09-28.md`

After Core + positive pilot evidence, Courier should evolve toward:
- signed Core/Security update channel;
- reusable Shared Capability Packs;
- optional Domain Packs;
- private-project isolation by default;
- content-addressed/deduplicated/delta delivery;
- weekly stable update windows;
- monthly capability/platform rollups;
- durable Time-Machine/rollback/Last-Known-Good history;
- explicit receive/contribute preferences;
- crypto agility and evidence-based post-quantum migration readiness.

Do not share customer/private repo content across users merely because it is useful. Only generalized, authorized, sanitized, tested, versioned capabilities may enter the shared distribution layer.

This direction must not delay current proof -> pilot critical path.


## Founder/company continuity rule

When the founder later asks for the plan, priorities, next step, overnight setup, company direction or launch sequence:

1. read this Master Control Plane;
2. read ops/ai/GATE_STATE_CURRENT.md;
3. read ops/ai/LIVE_STATUS_CURRENT.md;
4. read ops/ai/WALL_QUEUE_CURRENT.md;
5. read docs/FOUNDER_LIFE_AND_COMPANY_MASTER_PLAN_PUBLIC_SAFE_2026-09-28.md;
6. answer from durable current truth instead of asking the founder to retell prior conversations.

Public-safe company/founder planning belongs in the repo.
Sensitive private-life, credential, exact personal-finance, medical, family or private-customer data does not.
