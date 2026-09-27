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

1. finish/deduplicate wall + Extended Ledger preparation
2. final five-file candidate on accepted base
3. real targeted tests + exact 12-case matrix
4. Codex HIGH once on exact final SHA
5. Mac physical RUN_1
6. Mac physical RUN_2 restart/no-replay
7. Core Freeze
8. minimum honest pilot surface
9. first real pilot cohort
10. Product Shell only after positive pilot signal
11. Packaging/Updates after Core + pilot evidence
12. broader wall/connectors/Brain/community/world expansion only after proof

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
