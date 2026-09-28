# Google Windows Master 50 — Usage

## Recommended launch

Start 12-20 logical Google windows first, not 50 heavy jobs.

Suggested first wave:
01 Gate durability (ONLY one owner)
02 PRE_CODEX handoff
03 12-case evidence
04 targeted-test evidence
05 final scope binding
06 stale-evidence invalidation
07 result cache
08 claims/leases
09 harvester
10 Windows->Mac handoff
11 Mac binding inputs
12 RUN_1 command packet
13 RUN_1 evidence layout
14 A-once proof
15 trusted hash
16 server bytes
17 verify/reconcile
18 B auto-start
19 human relay
20 failed-execution

Second wave / when slots free:
21-40 proof, restart, Core Freeze, continuity, motor reliability.

Later phase:
41-50 motor/provider resilience, pilot, product gate, release/update, crypto agility, global routing.

## Scaling

These are long-running family masters.
Each may generate multiple bounded child tasks with unique done conditions and fingerprints.

Do NOT open 1,000 or 1,000,000 simultaneous heavy workers.
If you need more logical work depth, let these 50 masters generate child tasks.
That scales much better than creating millions of nearly identical prompt files.

MAX_HEAVY_JOBS=1 per host.
