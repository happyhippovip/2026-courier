# Model-Aware Wall Routing + Admission Policy — 2026-09-28

Status: CANONICAL
Inputs:
- ops/ai/COURIER_MODEL_CAPABILITY_REGISTRY_2026-09-28.md
- ops/ai/WORKER_SELF_IDENTIFICATION_AND_ROUTING_CONTRACT_2026-09-28.md
- ops/ai/DEVICE_ADAPTIVE_MOTOR_ADMISSION_2026-09-27.md
- ops/ai/COST_SAFE_GATE_TRANSITION_POLICY_2026-09-28.md

## Routing order

For each READY task:

1. Can C0 deterministic/local close it?
   YES -> route C0; do not spend model tokens.

2. Does task require explicit writer/runner authority?
   YES -> route exact C5 owner only.

3. Is task bulk/narrow/structured?
   YES -> route C1.

4. Is task independent review/reproducer/proof QA?
   YES -> route C2.

5. Is task fixed-candidate code-grounded gate review?
   YES -> route C3.

6. Is task genuine convergence/product/security judgment?
   YES -> route C4.

7. Otherwise:
   keep OPEN/UNKNOWN and let PREPARER refine task packet.
   Do not throw expensive models at vague tasks.

## Scorecard

Router may score candidates on:
- AUTHORITY_FIT: required, binary
- TASK_FIT: 0..3
- COST_EFFICIENCY: 0..3
- RESULT_REUSE: 0..3
- PROVIDER_AVAILABILITY: 0..2
- HOST_FIT: 0..2
- INDEPENDENCE_VALUE: 0..2
- DUPLICATION_RISK: 0..3 penalty
- GATE_OWNERSHIP_CONFLICT: disqualifying
- RESOURCE_PRESSURE: admission penalty

Never let a higher intelligence/capability score override missing authority.

## Reasoning-level selection

Default:
- C0: NONE/model-free
- C1: LOW/NORMAL
- C2: NORMAL/MEDIUM
- C3: HIGH for admitted fixed gate review
- C4: HIGH for admitted convergence task
- C5: level sufficient for exact owned task; authority and evidence matter more than prose reasoning

## Window-count selection

Window count is derived from:
- number of independent READY tasks of that class
- claims available
- host admitted motors
- provider quota/cost class
- duplication risk

Never derive window count from "available windows" alone.

Formula concept:
ADMIT = min(
  independent_ready_tasks,
  host_safe_motors_for_class,
  provider_budget_cap,
  task_family_parallel_cap
)

Global:
MAX_HEAVY_JOBS=1 per host unless later proven policy changes it.

Suggested expensive-model caps:
- C3 Codex: 1 per fixed gate fingerprint
- C4 Opus/Ultracode: small pool, typically 1-4; never wall-scale
- C5 physical runner: 1 physical run owner

## Automatic handoff

Every completed result must name:
NEXT_TASK_CLASS=
NEXT_PREFERRED_PROVIDER=
NEXT_PREFERRED_HOST=
NEXT_REASONING_LEVEL=
NEXT_WINDOW_COUNT=
NEXT_PROMPT_REF=

Harvester uses those as hints, not authority. Durable task/gate truth wins.

## Provider unavailable

If preferred provider unavailable:
- route to allowed fallback only if task packet says fallback class/provider is acceptable;
- otherwise WAIT_PROVIDER without resetting task identity;
- independent tasks for other providers remain READY.

## Cost guard

Before every model admission:
- check result cache/do-not-repeat fingerprint
- check gate cache
- check live claim
- check cheaper deterministic route
- check same-family active worker count

If any says duplicate/no-op:
do not admit model.

## Learning loop

After a task finishes, persist lightweight routing observations:
- provider/model class
- task class
- success/failure
- human correction needed
- approximate latency if available
- cost class, not private billing identifiers
- retry count
- evidence quality

Use this to improve routing later.
Do not automatically rewrite authority boundaries from performance observations.
