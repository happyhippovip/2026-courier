# Google Post-Indexer Prompt Pack — 2026-09-28

Use after Evidence Indexer reports all evidence families indexed and TRUE_IDLE.

Current known state:
FINAL_SHA=34b0a4264bf763bc2a78f761ffba36e47706b2cf
GATE_STATE=DURABILITY_PENDING

Recommended:
- Gate Durability Bridge: EXACTLY 1 Windows window, only if no owner exists
- Cross-Host QA: 2-4 windows
- Result Cache Integrity: 2-3 windows
- Proof Packet Assembler: 2-4 windows
- Non-Candidate Gap Closer: 3-8 windows
- TRUE_IDLE Escape Router: 1 window when deciding what a finished worker should do next

Do not run more Evidence Indexers for the same fingerprint.
