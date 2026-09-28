# Model Usage Telemetry Policy — 2026-09-28

Purpose: measure Courier model efficiency without publishing private account/billing data.

## Safe tracked fields
Per run/task/window, when the provider exposes them:
- provider class
- model class
- task/family id
- input_tokens
- cached_tokens
- output_tokens
- turns
- subagents_used
- result status
- useful findings count
- duplicate findings skipped
- wall-clock seconds
- evidence/result fingerprint

## Never commit to the public repo
- account names/emails
- subscription identifiers
- payment/billing details
- credit balances
- quota reset timestamps tied to an account
- API keys/tokens
- private chat content

## Efficiency metrics
Compute:
- cache_ratio = cached_tokens / input_tokens
- output_per_turn
- useful_findings_per_1m_input
- duplicate_skip_rate
- subagent_yield = useful unique findings / subagents_used
- model escalation rate
- result-reuse rate

## Storage
Tracked operational rollups may be committed under ops/ai/usage/ only when sanitized.
Raw provider/account screenshots and subscription quota panels stay local/private.

## Decision law
More tokens are not success.
Admit work only when it advances a concrete dependency-safe task.
Subagents are not assumed free and are counted as model work.
