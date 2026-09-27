# Courier Wall Rollout + Operator Protocol

Status: ACTIVE WORK PROCESS

## Goal

The human should not coordinate individual agents forever.

During bootstrap, the human may open a small number of provider windows. Courier must then use durable Markdown task packets, claims, results, the Ledger, and a Harvester so ordinary continuation no longer depends on copy/paste.

## How ChatGPT/Chief should instruct the operator

Every instruction should be given in this order:

1. HOST / PROVIDER
2. EXACT WINDOW COUNT
3. ROLE PER WINDOW
4. EXACT PROMPT TO PASTE
5. HOW MANY TIMES TO PASTE IT
6. WHAT, IF ANYTHING, TO RETURN TO CHIEF
7. STOP/RESOURCE CONDITION

Avoid vague directions such as "open several windows" or "let them work."

## Default bootstrap wall

For cost-sensitive build work, prefer:

- 1 PREPARER / PLANNER
- 2 EXECUTORS
- 1 HARVESTER

Total: 4 active light motors.

Increase only when the host remains smooth and the queue contains enough independent READY tasks.

Do not open more workers merely because provider quota exists.

## Normal future wall

Once role locking and harvesting are proven, all general worker windows should be able to receive the same universal master prompt.

The system chooses role based on durable state:

UNHARVESTED RESULTS -> HARVESTER
READY TASKS -> EXECUTOR
QUEUE EXHAUSTED + PREPARE LOCK FREE -> PREPARER
OTHERWISE -> IDLE

Specialist prompts remain available for debugging/bootstrap only.

## Human return protocol

The human should not paste every worker transcript back to Chief.

During bootstrap, return only:

- PREPARER summary when a new queue generation is created
- HARVESTER summary when contradictions/human gates exist
- CENTRAL WRITER final SHA/test gate
- physical RUN_1/RUN_2 result

Executor chatter should remain in durable result files.

## Cost rule

Prefer:
- exact task packets
- exact inputs
- result reuse
- cheap deterministic/local checks
- targeted tests
- subscription capacity before explicitly enabled PAYG

Avoid:
- broad repo reads
- repeated unchanged reads
- parallel duplicate reviewers
- idle analysis
- long narrative reports
- full test suites without a gate requiring them

## GitHub-first durability

Stable operating truth belongs in GitHub.

Local scratch is allowed for claims/checkpoints/results while a wall is running, but any rule that should survive machines/sessions must be represented by a stable repo entry or canonical queue pointer.

Do not rely on chat history as project truth.

## Build order

1. stable truth/path resolution
2. MD task packet contract
3. durable queue generation
4. atomic claim/lease
5. compact result record
6. automatic Harvester
7. Extended Execution Ledger
8. deterministic NEXT_READY
9. session/account continuity
10. provider/subscription/cost routing
11. device-adaptive admission
12. context checkpoint/clear/resume
13. Muse/Google adapter contract
14. targeted acceptance tests
15. one-prompt wall proof
16. physical RUN_1 / RUN_2
17. customer-facing wall controls

## Acceptance for "one prompt"

Do not declare the universal wall proven until:

- 4+ workers can receive the same prompt;
- no two live workers execute the same task;
- results are harvested without human relay;
- completed work survives /clear/new session;
- queue refresh does not broad-scan the repo;
- no provider/account change repeats completed work;
- resource guard can reduce admitted motors without losing queue state;
- queue empty becomes truthful IDLE.
