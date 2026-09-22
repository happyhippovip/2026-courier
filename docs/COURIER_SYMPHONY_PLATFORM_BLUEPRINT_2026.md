# Courier Symphony — Platform Blueprint 2026

Status: strategic target architecture. Implement incrementally; do not destabilize known-good runtime.

## North Star

Courier Symphony becomes a reliable AI operations platform that can run unattended across local machines and cloud workers while preserving auditability, safety, cost control, recovery, and reproducibility.

The product should feel simple to the user while the platform underneath provides strong operational guarantees.

## Core operating invariants

- Muse remains the primary execution worker for implementation work unless explicitly reassigned.
- One live mutable lane owner at a time.
- MAX_ACTIVE_EXTERNAL=1 until concurrency is separately proven safe.
- MAX_UNANSWERED_PROMPTS_PER_LANE=1.
- UNKNOWN locks the lane and prevents the next task.
- One task -> result -> persist -> verify -> reconcile -> DONE -> cooldown -> next.
- Never infer success from elapsed time alone.
- Never guess ownership, state, credentials, or security configuration.
- Reuse known-good checkpoints and backups before redesigning core behavior.

## Capabilities we intentionally adopt

### 1. Execution Ledger / Run Lineage

Every execution must be traceable end to end.

Record at minimum:

- task_id
- record_id
- attempt_id
- execution_id
- workflow_id
- workflow_version
- provider
- model / executor
- input artifact hashes
- prompt / instruction version
- context-pack version
- timestamps
- machine / worker identity
- admission decision
- estimated cost
- actual cost when available
- result hash
- persist status
- verification status
- reconciliation status
- final terminal state
- failure / blocker reason

Goal: one place can answer exactly what happened, where, with what version, for what cost, and whether the result is trusted.

### 2. Versioned Workflows

Stable production workflows are versioned artifacts, not loose prompts.

Examples:

- VIDEO_PIPELINE_v1
- RESEARCH_PIPELINE_v1
- AWS_WORKER_BOOTSTRAP_v1
- IMPORT_PIPELINE_v1
- NIGHT_RUN_v1

Requirements:

- immutable released versions
- draft versions for changes
- diff / compare
- rollback
- explicit promotion to production
- no silent behavioral changes

### 3. Context Packs

Each job receives only the context it needs.

A Context Pack can contain:

- project rules
- relevant files
- known-good state
- security policy
- provider policy
- current task state
- prior result references
- budget envelope

Requirements:

- versioned
- hashable
- minimal
- reproducible
- no plaintext secrets committed to Git

### 4. Provider / Executor Abstraction

Courier should route work through a stable internal executor interface.

Potential executors include:

- Muse
- other LLM providers
- local deterministic tools
- browser / computer workers
- cloud jobs

The controller must not depend on one provider's UI.

Provider fallback is allowed only when idempotency and UNKNOWN handling are proven safe.

### 5. API-first Production Interface

Once a workflow is proven, it can be exposed through a stable internal API.

Principle:

UI -> Courier API -> admission -> workflow -> executor -> ledger -> verified result

The API must be versioned and authenticated.

### 6. Cost Guard / Admission Control

Cost is part of the scheduling decision before execution.

For each task record:

- provider price class
- expected token / compute use
- expected runtime
- cloud worker cost
- daily / monthly budget remaining
- maximum permitted cost
- reason for admission or rejection

Support:

- per-task ceilings
- per-provider ceilings
- daily ceilings
- monthly ceilings
- emergency hard stop

### 7. Multi-cloud / Hybrid Worker Fabric

Do not bind Courier to one hosting provider.

Target roles:

- Controller: small, reliable, always-on Linux host
- Burst Worker: starts only when work requires it
- Mac / Windows: development, supervision, recovery, optional local execution

Provider selection should be based on:

- total monthly cost
- stop/start billing model
- storage price
- public IPv4 cost
- data transfer
- architecture compatibility (x86/ARM)
- security / IAM capabilities
- region / data location
- operational reliability

Infrastructure must be reproducible so controller or workers can move between providers.

### 8. Infrastructure as Code

Hard cloud configuration must be reproducible.

Store safe, non-secret definitions for:

- network
- security groups / firewall rules
- IAM / instance-role policy definitions
- machine bootstrap
- packages
- services
- environment structure
- monitoring
- restore steps

Prefer declarative templates and bootstrap scripts over undocumented manual console clicks.

### 9. Secrets Architecture

Never commit plaintext secrets.

Use:

- cloud instance roles / temporary credentials where available
- secret manager / keychain / encrypted store
- least privilege
- rotation
- auditable access

Separate configuration from credentials.

### 10. Observability

A production dashboard should expose:

- READY
- RUNNING
- WAITING
- UNKNOWN
- BLOCKED
- DONE
- active task
- current worker
- workflow version
- last successful completion
- last failure
- queue depth
- provider status
- current daily spend
- estimated monthly spend
- uptime
- duplicate / lost-result counters

Logs must support correlation by task_id / attempt_id / execution_id.

### 11. Recovery and Disaster Recovery

Maintain a portable Recovery Package containing:

- source version / Git refs
- infrastructure definitions
- bootstrap scripts
- service definitions
- dependency versions
- workflow definitions
- schema versions
- restore runbook
- health-check runbook
- SHA256 hashes
- backup manifest

Never include unencrypted passwords, API tokens, AWS keys, or private SSH keys.

Recovery objective: rebuild the platform from a clean machine without relying on undocumented memory.

### 12. Policy Engine

Admission rules must be machine-readable.

Examples:

- allowed providers
- allowed capabilities
- writable scopes
- required human approval
- budget limits
- time windows
- data sensitivity rules
- concurrency limits
- recovery behavior

The scheduler executes policy; it does not improvise policy.

### 13. Idempotency and Duplicate Protection

Every external action needs an idempotency strategy.

Required before scale-out:

- stable task identity
- stable attempt identity
- duplicate detection
- no silent collapse of conflicting records
- same ID + different content => conflict / fail closed
- resume from confirmed checkpoint
- UNKNOWN never triggers automatic duplicate submission

### 14. Evaluation / Quality Gates

Production workflows require explicit acceptance tests.

Track:

- functional correctness
- regression tests
- reliability
- duplicate rate
- lost-result rate
- latency
- cost
- human intervention rate
- recovery success

Promotion to production requires evidence, not intuition.

### 15. Grant / Due-Diligence Evidence Pack

Maintain continuously, not only before an application.

Evidence should include:

- architecture diagram
- problem statement
- product differentiation
- security model
- data-flow diagram
- reproducibility / recovery model
- test evidence
- reliability metrics
- cost model
- roadmap
- deployment architecture
- Git history / versioning
- operational runbooks
- risk register
- scalability plan
- measurable milestones

Do not claim guarantees or capabilities that are not proven.

## Product UX principle

The normal user experience should remain simpler than the underlying platform.

Users should not need to understand:

- provider-specific implementation
- run-size internals
- retry machinery
- cloud networking
- worker provisioning

The platform should expose clear states, actions, evidence, cost, and recovery.

## Implementation order

Do not build everything simultaneously.

### Phase A — Foundation
1. Finish secure cloud access.
2. Make infrastructure reproducible.
3. Establish reliable Machine A.
4. Establish Machine B only after A is proven.
5. Prove headless unattended runtime.

### Phase B — Trust Layer
1. Execution Ledger / Run Lineage.
2. Workflow versioning.
3. Context Packs.
4. Cost Guard.
5. Observability and audit correlation.

### Phase C — Platform Layer
1. Versioned internal API.
2. Provider/executor abstraction.
3. Policy engine.
4. Safe burst workers.
5. Portable deployment across providers.

### Phase D — Scale / Funding Readiness
1. Quality/evaluation dashboard.
2. Disaster-recovery drill.
3. Cost benchmark across providers.
4. Architecture + security evidence pack.
5. Demonstrable end-to-end unattended production run.
6. Measured reliability and cost-per-completed-task.

## What we explicitly do NOT do now

- no Kubernetes just for appearance
- no multi-region architecture before a real need
- no new orchestration framework while the current proven motor works
- no provider switching without compatibility evidence
- no broad concurrency before single-lane correctness is proven
- no huge UI redesign before the trust layer exists
- no speculative infrastructure spend for presentation value

## Funding principle

No funding outcome can be guaranteed.

The objective is to make Courier Symphony technically credible, auditable, reproducible, secure, measurable, and demonstrably useful so that an application can be supported by evidence rather than promises.

## Current priority

The current live priority remains:

secure AWS access -> reproducible cloud state -> Machine A -> Machine B -> headless runtime -> Execution Ledger.

This blueprint must not interrupt or overlap with the active AWS live-write lane.

## Universal API and Connector Architecture

Courier's platform layer now has a dedicated API/connector target architecture.

The guiding model is:

ANY INPUT
-> CANONICAL COURIER CONTRACT
-> ADMISSION
-> POLICY
-> COST GUARD
-> EXECUTE
-> RESULT
-> PERSIST
-> VERIFY
-> RECONCILE
-> DONE

Detailed specifications:

- [Universal API & Connector Blueprint 2026](./UNIVERSAL_API_CONNECTOR_BLUEPRINT_2026.md)
- [Connector and Capability Contract](./CONNECTOR_AND_CAPABILITY_CONTRACT.md)
- [Connector Security and Trust Model](./CONNECTOR_SECURITY_AND_TRUST_MODEL.md)

Planned protocol adapters include REST/OpenAPI, MCP, A2A, Webhooks/AsyncAPI/CloudEvents, streaming transports, and later commerce/payment/UI interoperability where justified.

The execution core remains protocol- and provider-neutral. External agents or connectors never bypass Courier admission, policy, cost, lineage, verification, reconciliation, or fail-closed behavior.

Current implementation order remains foundation first. API/connector implementation begins only after the secure cloud/runtime and trust-layer prerequisites are sufficiently stable.
