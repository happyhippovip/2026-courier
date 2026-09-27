# Provider Limit Fallback Prompt Pack — 2026-09-28

When a new provider-limit fingerprint appears:

1. Run exactly 1x:
   PROVIDER_LIMIT_RECOVERY_ROUTER_PROMPT.txt

2. Router chooses only among already-available authorized providers.

Fallback prompts:
- GOOGLE_PROVIDER_LIMIT_FALLBACK_100X_PROMPT.txt
- MUSE_PROVIDER_LIMIT_FALLBACK_100X_PROMPT.txt
- SONNET_PROVIDER_LIMIT_FALLBACK_100X_PROMPT.txt

3. If no already-available route can unblock the family:
   create one PROVIDER_ACCESS HUMAN_GATE for the operator.

4. Keep unrelated work running.

Suggested counts after router:
- Google fallback: 2-10 depending on READY work
- Muse fallback: 1-4
- Sonnet fallback: 1-4
- Opus: only for specifically routed high-value semantic review
