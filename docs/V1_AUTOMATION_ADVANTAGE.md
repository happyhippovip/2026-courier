# Courier Symphony — Automation Advantage Principle

Status: **PRODUCT / ORCHESTRATION PRINCIPLE**

Courier must not compete on "we can run a prompt every N minutes." Scheduled prompts, loops, cron jobs, background agents, and reusable skills are increasingly commodity capabilities.

Courier's durable advantage is the **guaranteed automation layer above those primitives**.

## 1. Commodity primitives are inputs, not the product

External tools may provide:
- recurring prompts;
- background scheduled tasks;
- skills;
- subagents;
- workflows;
- browser/terminal execution.

Courier may use or interoperate with such primitives during development, but the customer value must not depend on any one provider's scheduler semantics.

## 2. Courier's product-level automation contract

A Courier automation should progressively aim to provide all of the following:

### Durable intent

The user's intended outcome is represented durably and can survive:
- app restart;
- controller restart;
- worker restart;
- provider/session loss;
- device handoff.

### Canonical truth

The append-only Courier ledger remains authoritative.

A scheduler, model, UI, worker, or provider is never a second source of truth.

### Consequence-aware execution

Courier distinguishes:
- safe/idempotent work;
- retryable work;
- externally consequential work;
- ambiguous non-idempotent outcomes.

It retries only when the effect class and evidence make retry safe.

### Verified completion

"Agent said done" is not completion.

Completion requires the verifier/evidence contract appropriate to the task:
- result identity;
- artifact/effect evidence;
- freshness/fencing;
- integrity checks;
- deterministic state transition.

### Exactly-once effect protection

Courier prevents duplicate external effects through:
- dispatch fencing;
- attempt identity;
- result identity;
- idempotency/effect classification;
- stale/late-result rejection;
- durable reconciliation.

### Recovery without babysitting

When truth is known, Courier should recover automatically.

When truth is not known, Courier should stop safely and route to Human Desk instead of guessing.

### Replay and explanation

After restart or failure, Courier reconstructs state from durable truth and can explain:
- what was requested;
- what ran;
- what evidence exists;
- what failed;
- what was retried;
- what remains blocked;
- why human action is needed.

### Resource-aware autonomy

Automation must respect host health:
- bounded concurrency;
- no retry storms;
- event-driven idle behavior;
- adaptive backoff;
- explicit RESOURCE_PAUSE;
- exact owned-process cleanup;
- low idle power.

More autonomy must not mean more heat, leaked processes, or hidden polling.

### Self-refilling work without fake work

A long-running automation may derive new work from CURRENT evidence and user intent.

It must:
- deduplicate;
- preserve ownership;
- prefer the critical path;
- refuse artificial busywork;
- idle when no honest work remains.

## 3. Courier Autonomy Ladder

Product capability should climb this ladder in order:

1. **SCHEDULE** — something can run later.
2. **PERSIST** — intent and state survive restarts.
3. **FENCE** — only the valid worker/attempt can advance the task.
4. **VERIFY** — evidence, not narration, determines success.
5. **RECOVER** — known-safe failures recover automatically.
6. **RECONCILE** — uncertain outcomes become explicit, not blindly retried.
7. **EXPLAIN** — the customer can understand status without developer machinery.
8. **ADAPT** — concurrency, retry, and wakeups respond safely to system conditions.
9. **CONTINUE** — Courier can derive the next bounded work from current truth and user intent.
10. **ORCHESTRATE** — multiple tools/providers/devices can participate while Courier keeps one durable truth.

The Windows V1 does not need every future surface before EXE acceptance. The ladder is a direction and compatibility contract, not permission to skip the locked V1 route.

## 4. Daily automation-improvement loop

Every development day may harvest automation friction from real use.

For each observed friction:
1. capture the concrete failure or owner interaction;
2. classify it as COMMODITY_PRIMITIVE, COURIER_GUARANTEE_GAP, UX_FRICTION, or RESOURCE_SAFETY;
3. prove whether the current implementation already solves it;
4. if not, define the smallest durable improvement;
5. map it to exactly one L1-L6 owner;
6. add a targeted test or acceptance gate;
7. integrate only if it strengthens the locked route.

Do not add features merely to appear unique.

A useful improvement must do at least one of:
- remove owner babysitting;
- reduce duplicate/unsafe work;
- strengthen proof of completion;
- improve recovery;
- reduce resource cost;
- improve customer comprehension;
- preserve a future boundary that would otherwise require concrete rework.

## 5. Development evidence from current agent tools

Muse /loop and Antigravity scheduled tasks demonstrate that recurring execution itself is available outside Courier.

Therefore Courier should deliberately avoid treating "cron for agents" as the moat.

Our differentiation should be the combination of:
**durable intent + canonical ledger + fenced effects + verification + recovery + reconciliation + resource-aware continuation + customer-safe explanation**.

## 6. V1 scope discipline

For the current locked V1:
- L2 proves controller truth/recovery/API;
- L3 proves bounded worker/process ownership;
- L4 proves verifier/synthetic evidence;
- Golden Path proves lifecycle/failure/replay;
- L5 exposes canonical truth cleanly;
- L6 proves Windows EXE/clean-machine operation.

Only after those gates should real adapters and richer autonomous continuation become product implementation scope.

The principle is durable; the implementation order remains unchanged.


## 7. Domain Assurance Profiles

Courier's automation contract should become consequence-aware by domain.

Canonical companion:
`docs/V1_DOMAIN_ASSURANCE_PROFILES.md`

The long-term differentiator is not one generic agent policy for every task. It is one durable assurance kernel with stricter domain profiles for areas such as robotics, medical systems, and aviation.

Profiles determine proof obligations, authorization gates, retry/recovery rules, evidence requirements, and Human Desk conditions while preserving one canonical ledger.

The Windows V1 scope/order remains unchanged.


## 8. Commercial sustainability

Courier must become a sustainable business, not only an impressive engineering system.

Technical uniqueness is valuable only when it converts into customer value people will pay for and can be delivered with healthy operating economics.

Every major product improvement should eventually be evaluated against:
- customer pain removed;
- willingness to pay;
- retention / repeated use;
- cost to serve;
- support burden;
- gross-margin impact;
- whether it reduces owner babysitting;
- whether it creates a clearer paid tier, pilot, or enterprise value proposition.

Do not optimize for maximum autonomous compute if the customer value does not justify the cost.

Prefer product improvements that increase:
**verified useful work per euro of customer value and per euro of compute/support cost.**

Commercial discipline does not change the locked V1 implementation route. It means the Windows EXE, clean-machine acceptance, real adapters, and later domain assurance capabilities must be designed toward something customers can actually buy, trust, and keep using.

The company must be able to fund normal real-world obligations such as salaries/owner income, taxes, insurance, infrastructure, support, and continued product development.

Avoid both extremes:
- shipping unsafe or unfinished work merely for revenue;
- endlessly polishing technical novelty without proving a path to paying customers.


## 9. Anti-commodity horizon review

Courier should periodically re-evaluate its differentiation as external agent platforms add new commodity primitives.

Canonical review template:
`docs/v1/orchestration/OPUS_STRATEGIC_MOAT_REVIEW.md`

The rule is:

**do not chase features; protect guarantees.**

When a competitor ships scheduling, background agents, workflows, memory, computer use, or other execution primitives, ask whether Courier's customer value still survives if that primitive becomes universally available.

A durable differentiator should depend on guarantees such as:
- canonical truth;
- verified completion;
- exactly-once protection;
- consequence-aware recovery;
- reconciliation;
- domain assurance;
- evidence/change traceability;
- resource-aware continuation;
- customer-safe explanation.

If a proposed differentiator disappears when a commodity primitive becomes widespread, it is not a moat.

This review may create advisory proposals only. Implementation still follows the locked V1 route and one L1-L6 owner per change.

## 10. Ledger-is-not-the-moat correction

A durable ledger is necessary, but durable execution/checkpointing is increasingly available as infrastructure.

Therefore do not present "we have a ledger" as Courier's core differentiation.

The stronger product-level guarantee is the combination of:

**consequence semantics + verified completion + uncertainty reconciliation + replayable/explainable customer truth**

The journal is the foundation that makes those guarantees enforceable.

This distinction matters commercially: customers pay for trustworthy outcomes and reduced babysitting, not for the existence of an append-only data structure.

Canonical review harvest:
`docs/v1/orchestration/OPUS_MOAT_REVIEW_2026-10-01.md`
