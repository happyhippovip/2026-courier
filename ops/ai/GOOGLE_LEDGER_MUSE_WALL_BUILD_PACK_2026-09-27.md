# Google Ledger + Muse Wall Build Pack — 2026-09-27

Status: ACTIVE PREPARATION PACK
Purpose: finish the durable extended-Ledger specification and prepare a cost-controlled Muse wall queue without broad repo rereads.

## Global rules

- Windows Antigravity Central Writer remains the only final-candidate source writer.
- Google may write only coordination/spec/queue artifacts under ops/ai and local scratch for this pack.
- No broad repo census.
- No Get-ChildItem -Recurse over the repository.
- Read only explicitly named files.
- Reuse existing durable results instead of rereading source.
- No repeated unchanged reads.
- No idle analysis.
- No source edits outside explicitly authorized docs/ops artifacts.
- No account/billing/API-key changes.
- No automated account rotation.
- MAX_HEAVY_JOBS=1.
- The goal is to prepare tomorrow's Muse wall so Muse receives concrete READY tasks, not open-ended research.

## Extended Ledger target

The extended Ledger must be able to represent, without relying on chat memory:

GOAL
-> CONTRACT
-> TASK
-> ATTEMPT
-> CLAIM/LEASE
-> DISPATCH_GENERATION
-> PROVIDER_ROUTE
-> EXECUTION
-> RESULT_FINGERPRINT
-> ARTIFACT_EVIDENCE
-> TASK_OWNED_EXPECTED_SHA256
-> VERIFICATION
-> RECONCILIATION
-> NEXT_READY

It must also carry operational metadata needed for automatic continuation:

- queue_generation
- dependency_state
- owner/worker identity
- provider/auth_mode
- quota/cost guard state
- requested/admitted/active/guarded wall state
- workload_class
- context checkpoint/ref
- last_progress_at
- stop/block/throttle reason
- do_not_repeat fingerprint
- durable evidence refs

The Ledger must never store credentials or secret-bearing payloads.

## Window 1 — Google Ledger Writer

Role: docs/coordination writer, NOT final source writer.

Read only:
- docs/COURIER_SYMPHONY_CANONICAL_PRODUCT_PLAN.md
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md
- ops/ai/DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md
- ops/ai/NIGHT_QUEUE_NONINTERFERENCE_AND_COST_POLICY_2026-09-27.md
- schemas/thought_coverage_ledger.schema.json
- scripts/integration_contract.py only for field names, not broad analysis

Write:
- ops/ai/EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md
- ops/ai/MUSE_WALL_READY_TASK_LEDGER_2026-09-27.md

Deliver:
1. canonical field set
2. state transitions
3. idempotency/duplicate identity
4. queue-generation semantics
5. result/evidence refs
6. provider/cost/resource state
7. next-READY selection contract
8. exact Muse task-record format
9. implementation packet for Central Writer

Do not edit source code.

## Window 2 — Ledger Gap Mapper

Read only:
- ops/ai/EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md if present
- scripts/integration_contract.py
- server/app.py
- ops/ai/RETURNED_RESULT_POLICY.md

Task:
Map which required Ledger fields/states already exist and which are missing.
Do not propose unrelated architecture.

Output:
EXISTS=
MISSING=
AMBIGUOUS=
CENTRAL_WRITER_PACKET=
TESTS_NEEDED=

Write only local scratch result:
C:\Users\lol\courier_work\ledger_muse_prep\GLEDGER-02.result.md

## Window 3 — Muse Wall Task Generator

Read only:
- ops/ai/EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md
- ops/ai/MUSE_WALL_READY_TASK_LEDGER_2026-09-27.md
- ops/ai/GOOGLE_WINDOWS_NIGHT_QUEUE_50_2026-09-27.md
- existing durable Google result summaries only

Task:
Create a deduplicated Muse queue of concrete tasks for tomorrow.
Every task must include:
TASK_ID
PRIORITY
DEPENDENCIES
EXACT_INPUTS
EXACT_FILES_OR_RESULTS
ALLOWED_ACTION
DONE_CONDITION
EXPECTED_OUTPUT
RETEST_TRIGGER
DO_NOT_REPEAT_FINGERPRINT

Do not inspect source unless the task ledger explicitly says an input is missing.

Write:
ops/ai/MUSE_WALL_QUEUE_NEXT_2026-09-27.md

Target 30-50 logical tasks, not 30-50 physical windows.

## Window 4 — Cost + Token Guard Designer

Read only:
- ops/ai/NIGHT_QUEUE_NONINTERFERENCE_AND_COST_POLICY_2026-09-27.md
- ops/ai/SUBSCRIPTION_FIRST_AUTO_ROUTER_2026-09-27.md
- ops/ai/DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md
- ops/ai/MUSE_WALL_QUEUE_NEXT_2026-09-27.md if present

Task:
Define cost-sensitive Muse execution rules so a wall does not repeat broad reads.

Required:
- minimum-necessary-read rule
- result reuse
- per-task read budget
- no idle analysis
- no repeated repo census
- queue exhausted => idle/stop
- subscription-first
- PAYG explicit fallback only
- device-adaptive admitted motor count
- no duplicate execution on account/session change

Write:
ops/ai/MUSE_WALL_COST_GUARD_2026-09-27.md

## Window 5 — Result Harvester + Next READY

Read only:
- ops/ai/RETURNED_RESULT_POLICY.md
- ops/ai/EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md
- ops/ai/MUSE_WALL_QUEUE_NEXT_2026-09-27.md
- existing queue result summaries

Task:
Specify deterministic harvest behavior:
RESULT -> validate identity -> dedup -> attach evidence -> update Ledger -> reconcile -> compute next READY -> refill free logical slot.

Define:
- duplicate result fingerprint
- contradictory result handling
- stale result handling
- RETEST_AFTER_FINAL_SHA
- queue-generation migration
- no human relay normal path
- exact morning handoff record

Write:
ops/ai/MUSE_WALL_RESULT_HARVESTER_SPEC_2026-09-27.md

No source implementation.

## Window 6 — Tomorrow Boot Prompt Builder

Read only:
- ops/ai/EXTENDED_EXECUTION_LEDGER_SPEC_2026-09-27.md
- ops/ai/MUSE_WALL_QUEUE_NEXT_2026-09-27.md
- ops/ai/MUSE_WALL_COST_GUARD_2026-09-27.md
- ops/ai/MUSE_WALL_RESULT_HARVESTER_SPEC_2026-09-27.md

Task:
Produce one reusable Muse wall bootstrap prompt that can be pasted tomorrow and future days.

The prompt must:
- load only minimal durable truth
- claim next READY task
- avoid broad reads
- avoid duplicate work
- checkpoint durable result
- continue automatically
- survive /clear and new sessions
- preserve account/session-independent work identity
- stop on quota/resource/real gate
- never disturb Central Writer
- never change billing/auth
- remain useful with 4/5/6/8/9/10 admitted motors

Write:
ops/ai/MUSE_WALL_CONTINUOUS_BOOTSTRAP.txt

## Completion condition

This pack is complete when all six outputs exist or are explicitly BLOCKED with a concrete missing dependency.

Morning use:
1. inspect the six durable outputs
2. Central Writer consumes only exact implementation packets
3. Muse wall consumes MUSE_WALL_CONTINUOUS_BOOTSTRAP.txt
4. Muse workers pull concrete READY tasks from MUSE_WALL_QUEUE_NEXT_2026-09-27.md
5. Result Harvester semantics prevent manual copy/paste from becoming the normal scheduler
