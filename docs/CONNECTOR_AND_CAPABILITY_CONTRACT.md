# Courier Symphony — Connector and Capability Contract

Status: planned technical contract. Public-safe. This document defines the interface shape; it does not claim implementation.

## Purpose

Every Courier connector must expose capabilities through one consistent contract so that providers, business systems, agents, and protocols remain replaceable without changing the Courier execution core.

## Connector Manifest

Each connector should declare at minimum:

- connector_id
- name
- version
- publisher
- status
- trust_level
- protocol
- base capability namespace
- supported regions
- dependencies
- authentication methods
- required scopes
- network destinations
- data classifications handled
- rate limits
- timeout defaults
- retry semantics
- idempotency support
- webhook/event support
- streaming support
- recovery behavior
- deprecation status

## Capability Manifest

Each capability should declare:

- capability_id
- version
- description
- input_schema
- output_schema
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
- approval_default
- idempotency_mode
- timeout
- max_retries
- cost_class
- data_retention
- allowed_regions
- required_connector_scopes
- verification_method
- reconciliation_method

## Invocation Envelope

Every connector invocation should receive a normalized envelope containing:

- request_id
- task_id
- run_id
- tenant_id
- actor_id
- connector_id
- capability_id
- capability_version
- input
- attachments
- context_pack reference
- data_classification
- requested_permissions
- policy_decision reference
- budget
- deadline
- idempotency_key
- approval reference
- trace_context

## Result Envelope

Every result should distinguish:

- accepted
- running
- succeeded
- failed
- cancelled
- blocked
- unknown

Result data should include where relevant:

- provider request ID
- normalized output
- raw-result reference when retained
- artifact references
- side effects claimed
- cost/usage
- timestamps
- verification status
- reconciliation status
- retryability
- error class
- evidence references

A provider saying "success" is not sufficient proof of a consequential side effect.

## Authentication and Secrets

A connector must not require an agent to read raw credentials when a brokered or referenced credential can be used.

Preferred order:

1. workload/service identity
2. short-lived delegated tokens
3. OAuth grants
4. managed secrets
5. static credentials only when unavoidable and tightly controlled

Secrets must not appear in public Git, normal logs, artifacts, or analytics.

## Scopes and Permissions

Permissions must be capability-specific.

Examples:

- read metadata
- read content
- create draft
- send external message
- create object
- update object
- delete object
- execute infrastructure change
- spend funds

Broad "full access" scopes require explicit justification.

## Idempotency

Every consequential write capability must define one of:

- provider-native idempotency
- Courier-side deduplication
- deterministic reconciliation
- explicit non-idempotent classification requiring stronger approval

Same idempotency key + different content is a conflict and must fail closed.

UNKNOWN never automatically triggers duplicate submission.

## Retry Contract

Retry behavior must classify errors as:

- safe_retry
- retry_after
- blocked
- permanent
- unknown

Use bounded exponential backoff with jitter where appropriate.

Never retry irreversible or non-idempotent actions without proof that retry is safe.

## Rate Limits

Connectors should expose:

- quota window
- remaining quota when observable
- reset information
- provider retry-after signals
- Courier local throttling state

Courier must be able to queue or reject rather than blindly hammer a provider.

## Timeouts and Cancellation

Each capability should define:

- connection timeout
- execution timeout
- overall deadline
- cancellation support
- cleanup behavior
- state after timeout

Timeout does not imply failure; uncertain outcomes must be marked UNKNOWN until reconciled.

## Events and Webhooks

If a connector emits events, it should define:

- event types
- schema version
- delivery ID
- event ID
- timestamp
- signature mechanism
- replay protection
- retry policy
- ordering guarantee or lack of guarantee

Events should map into the canonical Courier event model.

## Verification

Write capabilities should define how Courier verifies the side effect.

Examples:

- refetch created resource
- compare version/etag
- read delivery receipt
- query provider transaction state
- confirm remote object hash
- confirm cloud resource state

Verification should be stronger for irreversible, financial, infrastructure, and destructive actions.

## Reconciliation

If claimed state and observed state differ, the connector must provide enough information for Courier to:

- retry verification
- classify UNKNOWN
- compensate where safe
- pause for approval
- record evidence
- avoid blind duplication

## Versioning

Connector and capability versions are immutable once released.

Breaking changes require a new major contract version or equivalent explicit migration.

Run Lineage must retain the exact connector and capability version used.

## Conformance Tests

A connector should pass automated tests covering:

- schema validation
- authentication failure behavior
- least-privilege permissions
- read/write classification
- rate limiting
- timeout handling
- idempotency
- retry safety
- cancellation
- event signatures
- verification
- reconciliation
- secret leakage checks
- redaction
- sandbox restrictions

## Browser / Computer-Use Connectors

Browser automation is a fallback adapter, not a privileged bypass.

It must still provide:

- declared capability
- explicit target
- allowed actions
- side-effect classification
- screenshot/evidence references when appropriate
- verification
- reconciliation
- timeout
- cancellation
- UNKNOWN handling

## Rule

A connector may extend Courier reach, but it may never weaken Courier execution semantics.
