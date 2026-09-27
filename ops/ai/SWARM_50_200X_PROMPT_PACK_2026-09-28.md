# 50-200x Swarm Prompt Pack — 2026-09-28

Each prompt is safe for many logical slots only because claims/fingerprints are checked before analysis.

## Prompts
- `ops/ai/swarm200/GOOGLE_LEDGER_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/GOOGLE_PROOF_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/GOOGLE_RESTART_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/GOOGLE_CONTINUITY_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/GOOGLE_MAC_PREP_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/MUSE_QA_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/MUSE_LEDGER_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/MUSE_PROOF_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/GOOGLE_PILOT_PREP_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/GOOGLE_PRODUCT_BACKLOG_SWARM_50_200X_PROMPT.txt`
- `ops/ai/swarm200/UNIVERSAL_PHASE_AWARE_SWARM_50_200X_PROMPT.txt`

## Suggested use
- Start 20-30 slots per family only when that many unique READY tasks exist.
- Scale toward 50/100 only from observed unique unclaimed backlog.
- 200 is a logical ceiling/backlog pattern, not a recommendation for 200 simultaneous heavy jobs.
- MAX_HEAVY_JOBS=1 per host.
- If no unique task exists, slot must idle without token-consuming analysis.
