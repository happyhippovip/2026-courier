# Courier Model Capability Registry — 2026-09-28

Status: CANONICAL ROUTING INPUT
Purpose: choose the cheapest/safest model class that can truthfully complete a task, then preserve expensive models for work where their additional reasoning changes a gate or decision.

This registry describes Courier roles, not vendor marketing rankings. Model/provider capabilities may change; workers must self-report their actual runtime identity and available mode when known.

## Capability classes

### C0 — DETERMINISTIC_LOCAL
Use for:
- git/hash/json/schema checks
- exact file existence/path resolution
- py_compile
- targeted pytest already specified
- result fingerprinting/dedup
- queue/claim bookkeeping

Preferred execution:
shell / Python / git / pytest before any model reasoning.

Model call should be avoided when C0 can finish the task.

### C1 — BULK_STRUCTURED_WORKER
Use for:
- narrow read-only queue execution
- exact evidence extraction
- result harvesting
- bounded test interpretation
- checklist completion
- task packet preparation from known truth

Current preferred providers:
- GOOGLE_CLI
- MUSE when task is review/reproducer oriented

Reasoning setting:
LOW or NORMAL where exposed.
Do not spend high reasoning on deterministic work.

### C2 — INDEPENDENT_REVIEWER
Use for:
- contradiction hunting
- independent synthesis
- replay/restart semantics review
- proof-card/core-freeze evidence review
- cross-host continuity review

Current preferred providers:
- MUSE
- OPUS class when the decision quality materially benefits and duplicate work is prevented
- GOOGLE_CLI for cheaper deterministic-first review

Reasoning setting:
NORMAL/MEDIUM by default.
HIGH only when a real unresolved semantic decision remains.

### C3 — SPECIALIST_CODE_REVIEWER
Use for:
- final code-grounded review on a fixed candidate
- difficult causal defect review
- security/release review of concrete implementation

Current preferred provider:
- CODEX

Current canonical rule:
CODEX HIGH exactly once for the fixed final candidate after PRE_CODEX is durably READY, unless a material source delta invalidates that review.

### C4 — CONVERGENCE_JUDGE
Use for:
- high-level convergence judgment
- product/security semantics where multiple valid interpretations remain
- deciding which unresolved conceptual gap is causal

Current preferred provider:
- OPUS / ULTRACODE class

Use sparingly.
Do not use for routine queue work, archaeology, repeated summaries, or deterministic checks.

### C5 — AUTHORIZED_WRITER_OR_PHYSICAL_RUNNER
Use only under explicit ownership.

Current roles:
- Windows Antigravity Central Writer: final-candidate application source writer
- Mac Antigravity: physical RUN_1 / RUN_2 runner after gates

This is an authority class, not a model-quality ranking.

## Current named profiles

### GOOGLE_CLI
Default class: C1
Strengths:
- high-volume structured queue work
- deterministic-first checks
- targeted tests
- ledger/replay/trusted-content task execution
- harvesting/synthesis when narrowly scoped

Avoid:
- duplicate expensive semantic reviews
- final application source mutation without explicit authority
- repeated gate rediscovery

Default reasoning: LOW/NORMAL
Preferred concurrency: many logical slots, device-adaptive admitted motors
MAX_HEAVY_JOBS=1 per host

### MUSE
Default class: C2
Strengths:
- independent QA
- reproducer/reviewer
- contradiction/stale-evidence review
- restart/run proof preparation
- proof/core-freeze review

Avoid:
- routine source writing
- rechecking already-proven CLI/stdout contract without trigger
- duplicate PRE_CODEX validation

Default reasoning: NORMAL/MEDIUM
Escalate to HIGH only for a real unresolved semantic blocker.

### CODEX
Default class: C3
Strengths:
- code-grounded review against exact source/tests/diff

Canonical use:
- fixed final SHA
- exact diff/scope
- real tests
- HIGH once

Avoid:
- bulk queue work
- early archaeology
- repeated review of unchanged SHA

### OPUS_4_6 / OPUS / ULTRACODE class
Default class: C4
Strengths:
- convergence
- semantic consistency
- complex proof/product/security judgment

Avoid:
- deterministic test execution
- broad queue consumption
- repeated gate checks
- source writing merely because it is capable

Default reasoning: HIGH only for admitted C4 tasks.
Recommended active windows: small bounded pool, not wall-scale.

### WINDOWS_ANTIGRAVITY_CENTRAL_WRITER
Default class: C5_WRITER
Authority:
- only final-candidate application source writer until durable truth changes ownership

Use:
- smallest causal source changes
- exact authorized file scope

### MAC_ANTIGRAVITY_PHYSICAL_RUNNER
Default class: C5_RUNNER
Authority:
- physical proof runner after exact binding and review

Use:
- RUN_1
- RUN_2
- physical runtime evidence

### CHATGPT_CHIEF / COORDINATOR
Default class: ROUTER/CHIEF
Use:
- operator-facing routing
- WHERE -> WINDOW -> ACTION -> COUNT
- resolve orchestration gaps
- update durable routing policy

Not normal execution motor.

## Unknown/future provider

If provider/model is not in this registry:
1. SELF_IDENTIFY actual model/provider/version/mode if available;
2. declare known tools and write authority;
3. start at conservative class C1_READ_ONLY;
4. do not grant source-write or physical-run authority by self-claim;
5. run one bounded representative task;
6. persist observed capability/result/cost class;
7. only then expand eligible task classes.

Never assume a new model is "best" because of its name.

## Router objective

Choose:
CHEAPEST_CAPABLE_SAFE_MODEL
subject to:
- task authority
- evidence requirements
- host/resource limits
- provider availability
- cost ceiling
- noninterference
- do-not-repeat fingerprint
- gate ownership

Expensive models are admitted only when cheaper/deterministic work cannot truthfully close the task or when independent high-quality judgment is itself the task.
