# Reliable Replenishing Swarm Usage

Use these instead of prompts that terminate on SLOT_IDLE.

## Best single prompt
ops/ai/RELIABLE_REPLENISHING_SWARM_MASTER_PROMPT.txt

## Local-first / sleep version
ops/ai/RELIABLE_LOCAL_FIRST_SLEEP_AUTOPILOT_PROMPT.txt

## Dedicated taskbank producer
ops/ai/DEEP_REAL_TASKBANK_EXPANDER_PROMPT.txt

Use 1-2 PREPARER expanders maximum at once.

## Lightweight universal worker
ops/ai/UNIVERSAL_NEVER_STRAND_WORKER_PROMPT.txt

Can be pasted into many logical slots.

## Scaling
Start 20-50 logical workers.
Increase only when durable taskbank has enough unique unclaimed packets.
100/200/1000 logical slots are fine as a capacity model, but not as simultaneous heavy processes.
The taskbank expander replenishes from real work; it never manufactures filler to satisfy a numeric target.

MAX_HEAVY_JOBS=1 per host.
