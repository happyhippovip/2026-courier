# Courier Overnight Wall — Smooth 10-Hour Policy — 2026-09-26

Status: PRODUCT/OPERATIONS REQUIREMENT  
Does not override current final-candidate proof gates.

## Goal

Prepare Mac and Windows to do useful unattended Courier work for up to **10 hours** while the user sleeps.

Priority:

**smooth verified throughput > maximum visible concurrency**

A stable 10-slot wall for 10 hours is better than a laggy 16-slot wall that overheats, swaps, duplicates work or stalls.

## Requested vs admitted capacity

Users may request an exact logical wall size.

Runtime continuously distinguishes:

- REQUESTED
- ADMITTED
- ACTIVE
- WAITING
- GUARDED
- RESERVED_INTERACTIVE
- IDLE

The host may admit fewer than requested based on real resource/provider/cost state.

## Adaptive host ceiling

Do not hard-code "Mac 16" or "Windows 16" as a promise.

Each host should discover a safe operating ceiling using lightweight signals:

- CPU/load trend
- memory pressure
- swap/pagefile pressure
- owned process count
- provider/API health
- recent task latency
- thermal/resource guard signals when actually measurable

If pressure rises:
1. stop admitting new work;
2. let bounded owned work finish or checkpoint;
3. reduce admitted logical slots;
4. move remaining capacity to WAITING/GUARDED;
5. continue light work if safe.

If the host stabilizes for a meaningful interval, capacity may increase gradually.

## Heavy work

Logical slots are not heavy jobs.

Current hard default:
MAX_HEAVY_JOBS=1

Heavy work must stay separately admitted and bounded.

Many logical/read-only slots may coexist only while they remain lightweight.

## Ten-hour round

OVERNIGHT_ROUND_HOURS=10

The round may end earlier for:

- no dependency-safe READY work
- provider unavailable
- cost/quota guard
- resource guard
- ownership ambiguity
- money/permission/human gate
- repeated-state/no-progress detection

Do not invent work to fill ten hours.

## Context hygiene during long rounds

Long wall sessions must checkpoint and rotate/clear context before it becomes bloated.

Preferred pattern:

WORK PACKAGE
-> DURABLE RESULT
-> LEDGER/CHECKPOINT
-> CONTEXT COMPACT/CLEAR WHEN STALE
-> LOAD NEXT MINIMAL PACKAGE
-> CONTINUE

Do not keep one gigantic chat alive solely to preserve history that already exists durably in the repo.

## Reserved interactive capacity

The user may reserve one or more slots for live interaction/coordinator work.

Example:
WALL_SIZE=10
RESERVED_INTERACTIVE=2
AUTONOMOUS_TARGET=8

Overnight mode may use a different reserve count chosen by the user.

## Success metric

Optimize:

VERIFIED_PROGRESS_PER_WALL_CLOCK
VERIFIED_PROGRESS_PER_COST
HUMAN_RELAY_COUNT -> 0

Do not optimize "number of open windows."
