# Courier Wall System — MD-First Durable Work Pipeline

Status: CANONICAL WALL OPERATING ENTRY POINT

## Why this exists

Courier wall work must not depend on chat memory, repeated repository discovery, or the human remembering which window was doing what.

The wall is driven by durable Markdown task packets plus Ledger state.

Core flow:

GOAL
-> CANONICAL TRUTH
-> MD TASK PACKETS
-> READY QUEUE
-> CLAIM
-> EXECUTE
-> RESULT
-> HARVEST
-> LEDGER
-> NEXT READY

## Stable entry points

Workers should start here instead of guessing dated paths.

- Wall system: `ops/ai/WALL_SYSTEM.md`
- Current queue pointer: `ops/ai/WALL_QUEUE_CURRENT.md`
- Task packet contract: `ops/ai/WALL_TASK_PACKET_SCHEMA.md`
- Universal worker prompt: `ops/ai/UNIVERSAL_MD_WALL_MASTER_PROMPT.txt`
- Wall rollout/operator protocol: `ops/ai/WALL_ROLLOUT_AND_OPERATOR_PROTOCOL.md`
- Current wall build queue: `ops/ai/WALL_BUILD_QUEUE_V1.md`
- Google wall system builder: `ops/ai/GOOGLE_WALL_SYSTEM_BUILDER_MASTER_PROMPT.txt`
- Cost/noninterference: `ops/ai/NIGHT_QUEUE_NONINTERFERENCE_AND_COST_POLICY_2026-09-27.md`
- Returned-result policy: `ops/ai/RETURNED_RESULT_POLICY.md`
- Mac Google permanent worker: `ops/ai/MAC_GOOGLE_PERMANENT_WORKER_PROMPT.txt`

## MD-first rule

Before a wall worker receives work, the task must exist as a durable Markdown packet.

Do not send open-ended prompts such as:
- "find something useful"
- "read the repo"
- "check everything"
- "continue researching"

A valid task packet names exact inputs, dependencies, allowed action, read budget, output, done condition and do-not-repeat fingerprint.

## Three wall roles

### PREPARER

One worker prepares or refreshes the next queue generation from durable truth and prior result summaries.

It may write wall task packets and queue manifests.
It must not edit application source.

### EXECUTOR

Many admitted workers claim READY task packets and execute only their declared scope.

They do not invent work and do not broaden reads.

### HARVESTER

One worker validates returned result identity, deduplicates findings, updates durable Ledger/queue state, and makes newly unblocked tasks READY.

The human is not the normal result router.

## Stable truth resolution

The human is not a path resolver.

Resolve repo root with:

`git rev-parse --show-toplevel`

Then use stable wall/truth indexes.

If a referenced path is missing:
1. check stable index/pointer;
2. check explicit supersession metadata;
3. use narrow Git path/history lookup if needed;
4. record TRUTH_CONFLICT when authority is ambiguous;
5. ask the human only when the unresolved conflict blocks a consequential action.

Never use a broad repo or disk scan to find the truth.

## Cost law

Default:

- MINIMUM_NECESSARY_READS=YES
- RESULT_REUSE_FIRST=YES
- NO_BROAD_REPO_SCAN=YES
- NO_REPEATED_UNCHANGED_READS=YES
- NO_IDLE_ANALYSIS=YES
- NO_DUPLICATE_REVIEW=YES
- QUEUE_EMPTY_MEANS_IDLE=YES

A provider call should advance one concrete READY task or record a real blocker.

## Queue generations

Every queue generation has:
- generation_id
- created_from_truth_fingerprint
- created_from_result_fingerprints
- task list
- supersedes_generation
- created_at
- status

A new session or provider account must not reset queue completion.

Completed task IDs remain completed unless a newer task explicitly has a RETEST_TRIGGER.

## Claims

One live claim per task.

Claim identity binds:
- queue generation
- task id
- worker id
- provider
- attempt
- claimed_at
- lease_until

A worker never steals a live claim.

## Results

Every task produces one compact durable result record with:
- task identity
- status
- inputs actually read
- commands/tests run
- evidence refs
- output artifact
- blocker
- do-not-repeat fingerprint
- next dependency impact

Large source content is not copied into result files.

## Noninterference

Wall workers must not disturb:
- Central Writer
- another live claim
- Mac proof runner
- servers/verifiers owned by another task
- account/billing/auth state

Application source writes remain under explicit writer ownership.

## Device-adaptive motors

Logical wall size is not active process count.

Requested wall may be 10 while admitted motors are 4, 5, 6, 8, 9 or 10.

The queue remains durable regardless of how many motors are admitted.

## Context rotation

SESSION MEMORY IS CACHE.
REPO + LEDGER + TASK PACKETS ARE DURABLE TRUTH.

When context becomes stale:

RESULT/CHECKPOINT
-> /clear or fresh session
-> read WALL_SYSTEM.md
-> read WALL_QUEUE_CURRENT.md
-> claim next READY task
-> continue

## Completion

When no READY task exists:
- do not invent work;
- one PREPARER may refresh from durable truth/results;
- if no new concrete work exists, wall becomes IDLE.

That is correct behavior, not failure.
