# Muse Wall Execution Pack — Google Prep -> Muse Ordered Wall -> 100-200x Swarm

## Stage 1 — Google prep

Prompt:
ops/ai/GOOGLE_PREPARE_MUSE_WALL_PROMPT.txt

Recommended:
- 1 window normally
- 2 windows maximum if one handles MPREP-01..05 and one MPREP-06..10
- do not use more than 2 preparers

Goal:
produce a compact unique Muse taskbank and skip fingerprints.

## Stage 2 — Muse ordered wall

Prompt:
ops/ai/MUSE_WALL_ORDERED_SEQUENCE_PROMPT.txt

For the prepared 30-window wall:
- 6 Ledger
- 4 False Green
- 4 Cross-provider/host continuity
- 4 Restart/no-replay
- 4 Carryover/general QA
- 4 Proof/Core-Freeze/current Muse/EITHER
- 3 reusable router workers
- 1 spare/router worker

If a family has fewer unique tasks than slots, excess slots must take another family or become SLOT_IDLE.

## Stage 3 — universal 100-200x logical swarm

Prompt:
ops/ai/MUSE_UNIVERSAL_CLAIM_FIRST_SWARM_100_200X_PROMPT.txt

Use only after:
- Google prep/taskbank exists
- claims/results are durable
- family routing is working

Recommended usage:
- paste into 30 slots first
- scale to 50 only if at least 50 unique unclaimed C2 tasks exist
- scale to 100 only if at least 100 unique unclaimed tasks exist
- 200 is a logical ceiling/backlog pattern, not a target for simultaneous active model work

The universal prompt is safe to reuse because every slot claims before analysis and idles instead of duplicating.

## Rule

Do not spend Muse capacity merely because capacity exists.
The objective is maximum unique verified progress per provider call.
