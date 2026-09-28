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
- Adaptive queue/package sizing: `ops/ai/ADAPTIVE_QUEUE_AND_PACKAGE_SIZING_2026-09-27.md`
- Muse wall preflight preparation: `ops/ai/MUSE_WALL_PREFLIGHT_PREPARATION_PACK_2026-09-28.md`

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


## Adaptive queue depth

Queue depth and active worker count are separate. Use `ops/ai/ADAPTIVE_QUEUE_AND_PACKAGE_SIZING_2026-09-27.md` to size task generations and package granularity for small, standard, and large hosts/users. Maintain a bounded READY reserve for unattended work only when real authorized independent work exists. Do not manufacture filler to hit a numeric target.


## Cost-safe gate transitions

Canonical policy: `ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md`
Current gate state: `ops/ai/GATE_STATE_CURRENT.md`

This policy overrides older prompt-local instructions that cause repeated validation or repeated `STOP_REASON=PRE_CODEX_GATE_REACHED` work.

Before model-powered gate work, reuse the durable gate fingerprint/verdict. One fingerprint gets at most one validation owner. A reported local SHA is not cross-host READY until durably resolvable. If the gate family is already closed for the same fingerprint, do not admit another worker to rediscover it.


## Model-aware routing

Canonical registry: `ops/ai/COURIER_MODEL_CAPABILITY_REGISTRY_2026-09-28.md`
Self-ID contract: `ops/ai/WORKER_SELF_IDENTIFICATION_AND_ROUTING_CONTRACT_2026-09-28.md`
Routing/admission policy: `ops/ai/MODEL_AWARE_WALL_ROUTING_POLICY_2026-09-28.md`
Universal router-worker prompt: `ops/ai/MODEL_AWARE_WALL_ROUTER_WORKER_PROMPT.txt`

Every admitted worker must self-identify provider/model/mode/authority, recommend the minimum sufficient reasoning level, and refuse tasks that are a poor/forbidden fit. Task packets declare preferred/allowed model classes and provider/host hints. The router prefers deterministic/local work first, then the cheapest capable safe model. Expensive reviewers are bounded and never used merely because windows are free.


## Provider-limit recovery

Policy: `ops/ai/PROVIDER_LIMIT_AND_HUMAN_GATE_POLICY_2026-09-28.md`
Recovery router: `ops/ai/PROVIDER_LIMIT_RECOVERY_ROUTER_PROMPT.txt`

One new limit fingerprint gets at most one recovery-router owner. Re-route only to already-available capable providers. If operator action is required, create one provider-access HUMAN_GATE and continue unrelated work.

## Family completion vs global idle

A specialized queue becoming empty is FAMILY_COMPLETE, not automatically TRUE_IDLE.

Required transition:
FAMILY_COMPLETE
-> persist family synthesis/result
-> release family claim
-> return to canonical router/master
-> inspect current durable pointers/results/claims once
-> claim another authorized compatible READY family when one exists
-> only then, if no READY work, no unharvested result, no unlocked synthesis/preparation, and no legal cross-family work remains, set GLOBAL_TRUE_IDLE.

Rules:
- A worker must not invent new tasks inside a completed family.
- A worker must not repeat the completed family merely to stay alive.
- A dedicated family prompt may terminate its family, but must emit NEXT_ROUTER=ops/ai/COURIER_PERMANENT_MASTER_WORKER_PROMPT.txt unless GLOBAL_TRUE_IDLE has been proven.
- Provider/model suitability still applies: wrong-fit work is routed, not executed.
- FAMILY_COMPLETE != GOAL_COMPLETE.
- TRUE_IDLE without a bounded global cross-family refresh is PREMATURE_IDLE.


## Working-only execution override

Canonical policy: `ops/ai/WORKING_ONLY_EXECUTION_POLICY_2026-09-28.md`.

For the direct Google IDE path, proven local execution is preferred over optional broken adapters/loaders. An unavailable optional tool is disabled from active routing rather than repeatedly repaired. Git remains durable source-control truth, but local read/write work does not require remote fetch/show unless remote durability is the task itself.

Direct Google IDE masters:
- `ops/ai/GOOGLE_IDE_MASTER_1_EXECUTE_CONTINUOUSLY_PROMPT.txt`
- `ops/ai/GOOGLE_IDE_MASTER_2_WORKING_ONLY_QA_REPAIR_PROMPT.txt`
- `ops/ai/GOOGLE_IDE_MASTER_3_FINISH_CRITICAL_PATH_PROMPT.txt`
