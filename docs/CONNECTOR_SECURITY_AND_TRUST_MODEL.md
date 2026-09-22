# Courier Symphony — Connector Security and Trust Model

Status: planned security model. Public-safe. Security claims must match actual implementation before publication as product capability.

## Principle

Default posture: **DENY**.

External systems are untrusted until explicitly classified, scoped, and admitted.

## Trust Levels

### Internal

First-party connector operated and maintained by Courier.

Requirements:
- code ownership known
- release provenance known
- least-privilege scopes
- conformance tests
- auditability
- emergency disable path

### Verified

Third-party or partner connector that has passed Courier review and conformance requirements.

Requirements should include:
- identity/provenance verification
- manifest validation
- permission review
- security scan
- dependency review
- behavior/conformance testing
- versioned release
- revocation path

"Verified" does not imply formal commercial partnership.

### Community

Public/community connector not fully verified by Courier.

Requirements:
- clear warning/classification
- sandbox
- strict egress rules
- least privilege
- no automatic high-risk approval
- kill switch

### Experimental

Prototype or evaluation connector.

Requirements:
- non-production default
- restricted tenants/environments
- strong logging
- reduced permissions
- easy rollback/disable

### Restricted

Connector permitted only for narrowly defined tenants, environments, regions, or capabilities.

### Deprecated

No new adoption. Existing use receives migration guidance and retirement timeline.

## Connector Sandbox

Untrusted connector code should run with:

- isolated process/container/runtime
- CPU and memory limits
- runtime deadline
- filesystem restrictions
- explicit network allowlist
- denied-by-default outbound access
- secret references rather than raw secret files
- no host-admin privileges
- no unrestricted cloud metadata access
- kill switch

## Supply Chain

Where feasible require:

- signed releases
- immutable version identifiers
- software bill of materials (SBOM)
- dependency scanning
- vulnerability scanning
- provenance metadata
- release changelog
- revocation capability

## Permission Manifest

Every connector must declare:

- required scopes
- target systems
- network destinations
- filesystem needs
- secrets used
- data classes handled
- write capabilities
- destructive capabilities
- financial capabilities
- infrastructure capabilities

Undeclared access is denied.

## Authentication

Prefer:

- OAuth/OIDC delegated authorization
- short-lived tokens
- service/workload identities
- managed cloud identities
- optional mTLS for service-to-service paths
- future workload identity federation where justified

Avoid long-lived static credentials when a safer mechanism exists.

## Authorization

Authorization must consider:

- tenant
- actor
- capability
- resource
- action
- data classification
- environment
- region
- budget
- approval state
- time/deadline
- trust level

Authentication alone never grants a capability.

## Token Handling

Rules:

- no blind token passthrough
- audience/scope must match the downstream service
- tokens should be short-lived where possible
- refresh tokens are treated as secrets
- token use is auditable
- revoked/expired credentials fail closed

## Secrets

Secrets must be:

- stored in a designated secret manager or credential broker
- referenced, not copied into prompts
- redacted from logs
- excluded from artifacts
- excluded from analytics
- rotated
- revocable

## Data Classification

Connectors should respect classifications such as:

- public
- internal
- confidential
- restricted

Policy may restrict which providers, regions, connectors, or storage locations may handle each class.

## Read vs Write

Read and write capabilities are separate.

High-risk write categories include:

- external communication
- destructive changes
- financial actions
- infrastructure changes
- permission/identity changes
- publication
- irreversible transactions

These require stricter policy and may require human approval.

## Approval

Approval decisions should bind to:

- exact capability
- exact resource or scope
- exact amount when financial
- exact tenant/actor
- expiry
- idempotency key
- task/run identity

A prior approval must not silently authorize materially different work.

## Webhook Security

Inbound webhooks require where supported:

- signature verification
- timestamp validation
- replay protection
- delivery/event ID tracking
- event schema validation
- source allowlist where useful
- bounded payload size
- safe parsing

## Egress Controls

Connectors should only contact approved endpoints.

Dynamic egress to arbitrary hosts is denied by default for untrusted connectors.

## Logging and Audit

Audit should record:

- actor
- tenant
- connector
- capability
- version
- scopes
- policy decision
- approval reference
- target
- timestamp
- side effect
- verification outcome
- reconciliation outcome

Sensitive payloads should be minimized or redacted.

## Kill Switch

Courier must be able to disable:

- one connector version
- one capability
- one tenant's access
- one provider route
- all writes for a connector
- the entire connector

Disable must not require modifying the connector's own code.

## Incident Response

A connector incident may trigger:

- immediate disable
- token revocation
- scope reduction
- credential rotation
- affected-run identification
- artifact/log review
- reconciliation of consequential actions
- customer/tenant notification where required
- patched version and controlled re-enable

## External Agent Boundary

Meta Muse, ChatGPT, Claude, Gemini, other agents, and future agent platforms are external callers unless explicitly running as trusted Courier-internal components.

They receive Courier capabilities, not unrestricted infrastructure control.

They must never receive direct AWS root credentials, SSH private keys, secret-store master keys, or unrestricted administrator shells.

## Existing Courier Invariants

This trust model cannot weaken:

- MAX_ACTIVE_EXTERNAL=1 until safe concurrency is proven
- MAX_UNANSWERED_PROMPTS_PER_LANE=1
- UNKNOWN => lane locked / fail closed
- no blind retry of consequential unknown actions
- persist -> verify -> reconcile before DONE

## Public Repository Rule

Never commit:

- credentials
- account IDs
- IP addresses tied to security rules
- internal provider pricing
- private partner terms
- secret routing weights
- exploit details that materially weaken production security
- confidential recovery details

Public architecture should describe principles without exposing attack-enabling operational specifics.
