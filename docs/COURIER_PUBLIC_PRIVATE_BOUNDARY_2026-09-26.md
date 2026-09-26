# Courier Public / Private Boundary — 2026-09-26

Status: release/demo guardrail.

## Principle

SHOW THE MAGIC, NOT THE MACHINERY.

Public material should make Courier's value understandable without exposing secrets, private customer data, or unnecessary proprietary implementation detail.

## Safe to show publicly when true

- a user goal in sanitized/plain language
- simple state such as working / reported / verified / finished / needs-you
- verified continuation from one step to the next
- restart/recovery outcome after it is physically proven
- privacy-safe Proof Cards
- opt-in call sign / public identity
- evidence-backed aggregate counts
- simple resource/capacity symbols without provider-secret detail

Every public claim must map to real evidence from the relevant run.

## Never public by default

- prompts / internal instructions / master prompts
- private filenames or file contents
- local usernames, repo paths, workspace paths
- API keys, verifier keys, signing keys, sessions, credentials
- customer data
- raw logs / raw artifact bytes
- provider account details
- private worker/host identifiers where not required
- unreleased architecture details that are unnecessary to prove the outcome
- private world/community strategy documents

## User != Public

A normal customer UI may contain private project/customer information.

Do not assume that hiding owner cards makes the underlying endpoint safe.

Public/social proof must use a separately redacted allowlist.

## Social sharing

Any later X/Facebook/social sharing is:
- opt-in
- previewed before publication
- based on evidence
- privacy-redacted
- never auto-posted merely because a task completed

## Community contributions

Future community tools/workflows/plugins must not gain unrestricted project or code-execution authority merely because they are signed or popular.

Future design must preserve:
- publisher/package identity
- explicit permissions
- versioning
- verification status
- revocation
- sandboxing or equivalent isolation where appropriate

No community backend is authorized before the core proof and early user validation.

## Private vision rule

The detailed Courier Symphony world/community concept remains outside the public repo.

Public files may contain only high-level safe guardrails:
- verified work over fake engagement
- reputation separate from paid capacity
- featherlight UX
- opt-in social proof
- future extensibility under explicit trust boundaries

## Pre-video check

Before posting a public demo:
1. verify the run is bound to the intended candidate
2. verify all displayed states/numbers from runtime evidence
3. remove paths/names/secrets/private content
4. hide raw logs/prompts/provider details
5. ensure reported != verified is not blurred
6. ensure no fake dashboard/demo activity is visible
7. review every frame for unreleased/private implementation detail
