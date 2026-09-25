# Courier Symphony — Confidential Strategy Policy

Status: standing internal operating rule.

## Purpose

Courier should aggressively learn from the public market while protecting the company's own confidential strategy.

The operating model is:

PUBLIC RESEARCH -> EXTRACT PRINCIPLE -> COURIER-SPECIFIC DESIGN -> IMPROVE -> TEST -> MEASURE -> KEEP / REJECT

## What counts as confidential strategy

Examples:

- unreleased roadmap priorities
- grant / funding drafts before submission
- internal pricing hypotheses
- provider cost benchmarks before publication
- unpublished architecture decisions
- internal reliability / failure metrics
- private partner or vendor discussions
- launch timing
- internal competitive assessments
- secret operational playbooks
- recovery procedures that expose sensitive infrastructure details
- credentials, tokens, keys, account-specific security details

## Storage rule

The GitHub repository is public.

Therefore actual confidential strategy must NOT be stored in this repository.

Reserved local-only paths:

- private_strategy/
- secret_notes/
- confidential/

These paths are ignored by Git.

For genuinely sensitive material, prefer encrypted storage rather than relying only on .gitignore.

## Competitive intelligence rule

We may study public websites, product flows, public docs, pricing, architecture patterns, UX, public talks, public demos, public repositories, and other lawful public material.

We may extract:
- principles
- patterns
- workflows
- design ideas
- operational lessons
- market positioning lessons
- reliability and cost concepts

We must not copy:
- proprietary source code
- non-public information
- trade secrets
- stolen/leaked data
- credentials
- private documents
- protected brand assets
- copyrighted copy or visual identity in a way that misrepresents ownership

Courier implementations must be original and adapted to our system.

## Provenance rule

For every important externally-inspired idea, keep a simple record:

- SOURCE
- DATE
- PUBLIC_OR_PRIVATE
- IDEA
- COURIER_ADAPTATION
- IMPROVEMENT
- TEST
- RESULT
- KEEP_OR_REJECT

If provenance is unclear, do not adopt directly.

## "Secret advantage" rule

Our defensible advantage should come from integration and execution quality, not secrecy alone.

Priority advantages:

- stronger fail-closed behavior
- better execution lineage
- lower cost per completed task
- reproducible infrastructure
- stronger recovery
- simpler UX
- better provider abstraction
- measurable reliability
- safer unattended execution
- faster iteration from idea -> evidence -> build -> verify
- better grant / partner evidence

## Partner truth rule

Do not claim Amazon/AWS, Meta/Facebook, or any other company as a formal partner unless documented.

Allowed when true:
- runs on AWS
- uses AWS services
- integrates with Meta APIs
- uses a Meta model
- optimized for AWS

## Access rule

Only the minimum people/agents that need confidential strategy should receive it.

Muse may use confidential strategy only when explicitly included in the active task context.

Do not paste secrets into unrelated tools, public issues, logs, screenshots, or repositories.

## Current priority

This policy must not interrupt the active AWS live-write lane.

Current path:
AWS secure access -> reproducible AWS state -> Machine A -> Machine B -> headless runtime -> Execution Ledger.
