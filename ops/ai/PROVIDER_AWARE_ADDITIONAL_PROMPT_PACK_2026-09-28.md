# Provider-Aware Additional Prompt Pack — 2026-09-28

## Sonnet
- SONNET_UNIVERSAL_MIDTIER_100X_PROMPT.txt
- SONNET_COST_ROUTING_REVIEW_100X_PROMPT.txt
- SONNET_PROOF_SEMANTICS_100X_PROMPT.txt

Suggested concurrent logical windows when Sonnet is actually available:
- Universal mid-tier: 2-6
- Cost/routing: 1-2
- Proof semantics: 2-4

## Provider-limit recovery
On a new limit fingerprint:
- 1 cheap classifier/router owner
- 0 automatic account-switch workers
- other providers continue normal READY work
- create HUMAN_GATE only if a manual access decision is genuinely needed

Never treat “baseline limit reached” as permission to discover/rotate accounts automatically.
