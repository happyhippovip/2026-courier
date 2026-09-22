# Courier Symphony — Universal API & Connector Blueprint 2026

Status: strategic target architecture. Public-safe. Implement incrementally; do not destabilize the known-good runtime.

## North Star

Courier Symphony becomes a universal execution fabric:

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

External agents, applications, users, companies, and machines may submit work through different protocols, but Courier normalizes every request into one internal contract and preserves the same execution, audit, recovery, cost, and safety semantics.

Core principle:

**Any agent. Any model. Any service. One reliable execution layer.**

## Current / Planned / Future

### CURRENT

- single-lane fail-closed execution invariants
- provider/executor abstraction as an architectural principle
- API-first direction
- Cost Guard / admission-control direction
- Execution Ledger / Run Lineage direction
- workflow versioning direction
- Context Packs direction
- AWS as preferred current cloud while architecture remains portable

### PLANNED

- canonical Task / Run / Artifact / Event contracts
- versioned public REST API
- OpenAPI
- Events / Webhooks
- OAuth/OIDC authorization
- Connector Adapter Interface
- Python and TypeScript SDKs
- MCP server/client compatibility
- A2A compatibility
- provider-adapter unification
- business-system connectors
- structured observability
- connector trust model
- capability-level approval engine

### FUTURE

- A2UI / AG-UI adapters where useful
- UCP commerce compatibility
- AP2-style agentic payment mandates/approvals where useful
- SCIM enterprise provisioning
- AuthZEN-compatible external authorization decisions
- SPIFFE-style workload identity
- public Connector / Capability Marketplace
- additional languages and industry connector packs

No item in PLANNED or FUTURE is to be publicly represented as already implemented.

## 1. Universal Connector Gateway

Courier should be able to accept or bridge, where appropriate:

- REST/HTTPS
- OpenAPI
- MCP
- A2A
- Webhooks
- AsyncAPI
- CloudEvents
- Server-Sent Events
- WebSockets
- gRPC / Protobuf
- GraphQL adapters
- A2UI
- AG-UI
- UCP
- AP2-style payment mandates
- OAuth / OpenID Connect / PKCE
- SCIM
- AuthZEN-compatible authorization interfaces
- SPIFFE-style workload identity
- OpenTelemetry

These standards are adapters around Courier. None may bypass Courier admission, policy, cost, verification, reconciliation, lineage, or fail-closed rules.

## 2. Canonical Courier Request Contract

Every inbound request should normalize to fields including:

- request_id
- task_id
- run_id
- tenant_id
- actor_id
- source
- capability
- capability_version
- input
- attachments
- context_pack
- data_classification
- requested_permissions
- policy_context
- budget
- deadline
- provider_constraints
- idempotency_key
- approval_requirements
- callback
- trace_context

The canonical contract must remain provider-neutral and protocol-neutral.

## 3. Public Data Plane

Planned public API resources include:

- GET /v1/capabilities
- POST /v1/tasks
- GET /v1/tasks/{task_id}
- POST /v1/tasks/{task_id}:cancel
- POST /v1/tasks/{task_id}:resume
- GET /v1/runs/{run_id}
- GET /v1/runs/{run_id}/events
- GET /v1/runs/{run_id}/artifacts
- GET /v1/runs/{run_id}/lineage
- POST /v1/workflows/{workflow_id}:run
- POST /v1/files
- GET /v1/artifacts/{artifact_id}
- GET /v1/approvals/{approval_id}
- POST /v1/approvals/{approval_id}:approve
- POST /v1/approvals/{approval_id}:reject
- webhook subscription management
- GET /v1/usage
- GET /v1/limits
- GET /v1/health

Public write capabilities must always remain constrained by capability-level authorization and approval policy.

## 4. Control Plane

The Control Plane is logically separate from the public Data Plane and governs:

- workflows and workflow versions
- Context Packs
- Connector Registry
- Provider Registry
- routing policies
- Cost Guard policies
- security policies
- approval policies
- tenant settings
- quotas and rate limits
- secret references
- audit
- evaluations and quality gates
- usage and billing
- retention
- data residency
- feature flags and rollouts
- connector versions and deprecations

The public Data Plane must never imply unrestricted administrative access to the Control Plane.

## 5. Protocol Discovery

Courier should expose machine-readable discovery where appropriate:

- /openapi.json
- /asyncapi.yaml
- /mcp
- A2A Agent Card
- /.well-known/ucp
- OAuth/OIDC discovery
- webhook schema registry
- capability manifest

Documentation should be generated from the same source of truth as runtime contracts where practical.

## 6. Execution Modes

The architecture must support:

- synchronous
- asynchronous
- streaming
- batch
- scheduled
- event-triggered
- webhook-triggered
- long-running
- human-in-the-loop
- approval-gated
- replay/recovery
- resume-from-checkpoint
- agent-to-agent delegation

A task may last milliseconds or days without requiring a different trust model.

## 7. Provider Abstraction

Courier should avoid hard-coding a single provider into the execution core.

Potential AI/model adapters may include, when actually integrated:

- OpenAI
- Meta model services / Muse-facing adapters
- Anthropic
- Google Gemini / Vertex AI
- Amazon Bedrock
- Azure AI
- Mistral
- Cohere
- xAI
- Groq
- Together
- Fireworks
- Hugging Face
- local / open-weight models
- future providers

Capability classes include:

- reasoning
- text generation
- structured output
- tool use
- computer use
- vision
- image generation
- video
- speech-to-text
- text-to-speech
- realtime audio
- embeddings
- reranking
- search
- research
- code execution
- browser execution

Provider adapters translate between Courier contracts and provider-specific formats.

## 8. Routing Engine

Routing may consider:

- requested capability
- measured quality
- historical success rate
- cost
- latency
- availability
- region
- data classification
- data residency
- context length
- modality
- tool support
- tenant policy
- provider outage state
- evaluation results
- budget

Fallback is allowed only when the substitute provider is semantically compatible and Courier idempotency/UNKNOWN rules remain intact.

## 9. Business Connector Layer

Connector families may include:

- AI/model providers
- Google Workspace
- Microsoft 365
- email and calendars
- communications
- developer tools
- cloud providers
- databases
- object storage
- vector stores
- data / analytics
- CRM
- ERP
- accounting
- support / ticketing
- commerce
- payments
- shipping
- marketing
- search

Examples may include Gmail, Outlook, Drive, OneDrive, SharePoint, Slack, Teams, GitHub, GitLab, Jira, Linear, Notion, Salesforce, HubSpot, Shopify, Stripe, Twilio, AWS, Azure, GCP, SQL and NoSQL systems.

These names describe potential integration targets, not current partnership or implementation claims.

## 10. Connector Precedence

Preferred integration order:

1. native API or open standard
2. MCP or A2A
3. event / webhook
4. controlled browser / computer-use fallback

Browser automation remains important for legacy systems and missing APIs, but it should not be the default when a stable machine interface exists.

## 11. Meta Muse

Meta Muse is treated as a potential Courier entry point, not as owner of Courier architecture.

A Muse-facing connector may receive only explicitly exposed Courier capabilities such as:

- courier.capabilities
- courier.submit_task
- courier.get_task
- courier.get_run
- courier.get_artifact
- courier.cancel_task

An external agent must never receive direct AWS root access, SSH private keys, unrestricted shell access, internal secrets, or database-root credentials.

No formal Meta partnership claim may be made without documented status.

## 12. MCP

Courier may act as both:

- an MCP server exposing selected Courier capabilities
- a controlled MCP client consuming approved external tools/resources

Requirements:

- trust classification for external MCP servers
- explicit separation of read and write capabilities
- no blind token passthrough
- secrets remain behind a credential broker or secret manager
- untrusted tool descriptions do not override Courier policy
- all consequential tool calls remain in Courier Run Lineage

## 13. A2A

A2A is appropriate when the counterparty behaves as an autonomous agent rather than a simple tool.

Courier should preserve:

- agent discovery
- capability discovery
- task delegation
- task status
- streaming
- artifacts
- cancellation
- long-running work
- push updates

Courier Run Lineage remains the authoritative execution record.

## 14. Event Model

Core events may include:

- task.accepted
- task.started
- task.blocked
- approval.required
- approval.granted
- connector.called
- connector.failed
- provider.selected
- provider.failed
- artifact.created
- result.persisted
- verification.passed
- verification.failed
- reconciliation.started
- reconciliation.completed
- task.completed
- task.failed
- task.cancelled

Events should carry Task, Run, Tenant, Actor and Trace correlation identifiers.

## 15. Webhooks

Webhook delivery requires:

- signatures
- timestamps
- replay protection
- delivery IDs
- idempotency
- retries with backoff
- dead-letter handling
- subscription filters
- event versions
- secret rotation
- pause/disable
- delivery logs
- test delivery

Delivery success and downstream processing success are separate states.

## 16. Reliability Contract

External actions inherit Courier reliability rules:

TASK
-> ADMISSION
-> POLICY
-> COST CHECK
-> EXECUTE
-> RESULT
-> PERSIST
-> VERIFY
-> RECONCILE
-> DONE

Mechanisms include:

- idempotency keys
- duplicate protection
- retry policies
- exponential backoff with jitter
- timeouts and deadlines
- cancellation
- circuit breakers
- rate-limit handling
- backpressure
- queueing
- checkpoints
- recovery
- dead-letter queues
- compensating actions
- side-effect verification
- reconciliation
- fencing / leases for future concurrent workers

Existing invariants remain authoritative:

- MAX_ACTIVE_EXTERNAL=1 until concurrency is separately proven safe
- MAX_UNANSWERED_PROMPTS_PER_LANE=1
- UNKNOWN locks the lane and prevents blind continuation or duplicate submission

## 17. Security and Authorization

Default posture: **DENY**.

Authentication and authorization are separate concerns.

Potential mechanisms:

- OAuth / OpenID Connect
- PKCE
- short-lived service tokens
- service identities
- optional mTLS
- future workload identity
- SCIM for enterprise provisioning
- RBAC + ABAC and, where justified, relationship-based rules
- external policy decision interfaces where useful

No external token is blindly forwarded to another service.

## 18. Secrets

Agents should be able to invoke a capability without reading its credential.

Use secret references and dedicated secret stores.

Rules:

- no secrets in Git
- no secrets in prompts unless technically unavoidable and explicitly controlled
- no secrets in normal run logs
- no secrets in artifacts
- no secrets in analytics
- prefer temporary credentials
- rotate connector credentials
- redact accidental secret leakage before persistence where feasible

## 19. Approval Engine

Each capability should declare properties such as:

- read_only
- write
- external_side_effect
- reversible
- irreversible
- financial
- communication
- infrastructure
- destructive
- sensitive_data
- privilege_escalation

Approval policy is derived from capability classification plus tenant policy and task context.

## 20. Cost Guard

Each task may have a cost envelope covering:

- model cost
- connector cost
- compute cost
- storage cost
- network cost
- search cost
- media cost
- retry cost
- human intervention

The Cost Guard may:

- choose another compatible provider
- use a smaller model
- batch work
- use cache
- pause
- request approval
- reject execution

Commodity intelligence should move toward the lowest sustainable cost through engineering, not loss-making pricing.

## 21. Batch, Cache and Change Detection

Where appropriate use:

- batch APIs
- prompt/result cache
- embedding cache
- connector cache
- conditional requests
- ETags
- change tokens
- delta APIs
- events instead of polling
- queue processing

## 22. Observability

OpenTelemetry-compatible traces, metrics, and logs are preferred as a neutral telemetry layer.

Important correlation dimensions include:

- run_id
- task_id
- workflow_version
- connector
- provider
- model
- latency
- cost
- retry_count
- approval_count
- result_status
- verification_status
- reconciliation_status

The Execution Ledger remains product truth; telemetry supplements it.

## 23. API Versioning

Public contracts require:

- explicit versioning
- no silent breaking changes
- deprecation notices
- migration guides
- transition periods
- usage telemetry
- retirement dates
- retained connector/workflow versions in lineage

## 24. Connector SDK

Initial planned SDKs:

- Python
- TypeScript

Potential later SDKs:

- Go
- Java
- others based on demand

Every connector manifest should describe:

- name
- version
- publisher
- capabilities
- input schema
- output schema
- authentication method
- scopes
- side effects
- read/write classification
- data classification
- costs
- rate limits
- timeouts
- webhook support
- idempotency support
- regions
- dependencies
- permissions
- recovery behavior

Connectors should pass automated conformance tests before receiving a trusted classification.

## 25. Connector Trust Levels

Planned trust levels:

- Internal
- Verified
- Community
- Experimental
- Restricted
- Deprecated

Untrusted or community connector code should be isolated and governed by:

- signed releases where feasible
- SBOM
- dependency scanning
- vulnerability scanning
- permission manifest
- network allowlist / egress controls
- sandboxing
- CPU/memory/runtime limits
- kill switch

## 26. Commerce

Courier should prepare for open commerce interfaces rather than hard-code individual shops.

Potential capability families:

- discovery
- cart
- checkout
- orders
- fulfillment
- returns
- invoices
- receipts
- subscriptions
- procurement
- B2B purchasing
- creator products
- workflow products

UCP compatibility may be adopted where it provides useful interoperability.

## 27. Payments

Payments are not ordinary tool calls.

Financial actions require, where applicable:

- mandate
- amount limit
- currency
- merchant identity
- purpose/description
- approval policy
- receipt
- audit trail
- idempotency
- fraud controls

AP2-style mandate/approval compatibility may be adopted where useful.

Courier should not store card data when a specialized payment provider can hold it.

## 28. Realtime and Multimodal

The API architecture must not be text-only.

Support should be possible for:

- text
- images
- video
- audio
- voice
- files
- structured data
- streams
- screens
- controlled computer interaction

## 29. Artifacts

Artifacts are first-class resources with metadata including:

- artifact_id
- run_id
- type
- MIME type
- hash
- size
- created_at
- producer
- provenance
- verification state
- retention
- access policy

Large outputs should be referenced rather than repeatedly copied into prompts.

## 30. Marketplace Future

A future Courier Capability Marketplace may allow developers to publish:

- connectors
- workflows
- Context Packs
- evaluation packs
- policy packs
- UI components
- specialized capabilities

Courier can provide:

- versioning
- sandboxing
- Run Lineage
- security classification
- billing
- revenue share
- recovery
- quality evidence from real executions

## 31. Economic Moat

Courier's defensible layer should come from:

- execution history
- Run Lineage
- connector ecosystem
- workflow assets
- recovery
- policy
- cost intelligence
- quality history
- provider routing
- provenance
- trust
- enterprise integrations
- marketplace liquidity

The moat should not depend on exclusive access to one model.

## 32. Public / Confidential Boundary

Public-safe:

- API concepts
- protocol support plans
- SDK plans
- connector architecture
- security principles
- status/changelog
- integration guides
- implemented capability docs
- real public metrics

Keep confidential:

- negotiated provider pricing
- internal routing weights
- internal margins
- non-public partner terms
- private security findings
- abuse heuristics
- secret fallback priorities
- credentials and account-specific infrastructure data
- unreleased funding drafts

## 33. Implementation Order

Do not build everything at once.

1. Canonical Task / Run / Artifact / Event contracts
2. Execution Ledger / Run Lineage
3. OpenAPI public contract
4. Events / Webhooks
5. OAuth / authorization
6. Connector Adapter Interface
7. Python + TypeScript SDK
8. MCP server/client
9. A2A endpoint
10. Meta Muse connector
11. provider-adapter unification
12. priority business connectors
13. UCP / AP2 compatibility where justified
14. Connector Marketplace

This roadmap must not interrupt the active secure-cloud foundation work.

## Non-negotiable rule

**Connect everything. Trust nothing by default. Verify every consequential result.**

A connector never controls Courier. Courier controls execution.
