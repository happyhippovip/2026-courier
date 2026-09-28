# Hard No-Idle 50 — Usage Plan

## Mac
Start 12 windows:
MAC 01-12.
When complete, reuse those windows for MAC 13-20.
Then MAC 21-25.

## Muse
Start 12 windows:
MUSE 01-12.
Then MUSE 13-20.
Then MUSE 21-25 when their phase is unlocked.

## Scaling
Do not run all 50 as heavy jobs.
These are logical workers.
MAX_HEAVY_JOBS=1 per host.

## Reliability
If a prompt reaches temporary empty work:
sleep -> refresh -> replenish -> continue.
SLOT_IDLE must not be treated as mission completion.
