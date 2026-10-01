# Additional Google Reusable Prompt Pack — 2026-09-28

Use only when router/current durable state says the family has real READY work.

## Either host
- GOOGLE_RESULT_HARVESTER_100X_PROMPT.txt
- GOOGLE_CLAIM_LEASE_100X_PROMPT.txt
- GOOGLE_COST_WASTE_100X_PROMPT.txt
- GOOGLE_CROSS_HOST_CONTINUITY_100X_PROMPT.txt
- GOOGLE_EVIDENCE_INDEXER_100X_PROMPT.txt
- GOOGLE_PILOT_READINESS_100X_PROMPT.txt

Suggested maximum concurrent logical windows per family:
- Harvester: 1-2
- Claim/Lease: 2-3
- Cost/Waste: 1-2
- Cross-host: 2-4
- Evidence Indexer: 2-4
- Pilot Readiness: 2-3

These are logical windows, not heavy jobs. MAX_HEAVY_JOBS=1 per host.

Before opening many windows, run:
ops/ai/AUTO_MODEL_WINDOW_ROUTER_PROMPT.txt

Never fill windows merely because capacity exists.
