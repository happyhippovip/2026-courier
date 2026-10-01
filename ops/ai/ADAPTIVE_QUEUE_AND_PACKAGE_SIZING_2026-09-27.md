# Courier Adaptive Queue Depth & Work-Package Sizing — 2026-09-27

Status: CANONICAL WALL OPERATING REQUIREMENT
Purpose: make Courier wall work useful on tiny, normal, and very large user setups without equating queue size with process count.

## Core distinction

Persist separately:
- LOGICAL_QUEUE_DEPTH
- READY_TASK_COUNT
- ADMITTED_MOTORS
- ACTIVE_MOTORS
- HEAVY_JOBS
- LIGHT_TASKS
- WAITING_TASKS
- TRUE_IDLE

Logical queue depth is backlog capacity.
It is NOT permission to spawn the same number of windows/processes.

## User-size principle

Courier must work for:

### SMALL
Examples:
- one laptop
- one provider/account
- 1-3 active workers
- short sessions

Behavior:
- smaller queue generations, typically 10-30 concrete tasks
- larger task packages where context/setup cost would dominate
- minimal coordination overhead
- aggressive RESULT_REUSE_FIRST

### STANDARD
Examples:
- one capable workstation or laptop
- several lightweight sessions
- 4-10 admitted motors

Behavior:
- queue generations around 30-120 tasks when real independent work exists
- balanced package sizing
- one heavy job maximum unless proven otherwise
- specialists only where scopes are clearly independent

### LARGE
Examples:
- multiple devices/providers
- many lightweight logical slots
- high overnight capacity

Behavior:
- deeper logical queues, potentially 100+ tasks
- smaller independent work packages when this reduces collision
- shard by evidence surface / dependency / host suitability
- never multiply the same analysis merely to fill capacity
- central harvest/dedupe remains authoritative

## Adaptive package-size rule

Choose package size from coordination cost versus task independence.

Prefer BIGGER packages when:
- reads/setup are expensive;
- work is serial or tightly coupled;
- one result naturally answers several adjacent checks;
- splitting would cause repeated context loading.

Prefer SMALLER packages when:
- checks are independently verifiable;
- many lightweight workers are safely available;
- outputs can be deduplicated cleanly;
- parallel work shortens the critical path.

Never split one causal question into many cosmetic tasks solely to inflate queue depth.

## Queue refill

When remaining READY depth falls below a practical reserve:

HARVEST
-> recompute dependencies
-> prepare one next generation from durable truth/results
-> size generation according to real uncompleted independent work

Do not wait for absolute zero if preparing the next generation is cheap and non-interfering.

But:
NO_SPECULATIVE_FILLER=YES
NO_BROAD_SCAN=YES

## Target reserve

A PREPARER may maintain a bounded logical reserve for unattended work when:
- current critical-path families are explicitly authorized;
- task scopes are concrete;
- completed fingerprints are known;
- no writer ownership is violated.

Reserve size is adaptive, not fixed.

Examples:
- SMALL: 10-20 READY reserve
- STANDARD: 30-60 READY reserve
- LARGE/OVERNIGHT: 60-150 READY reserve when genuinely independent work exists

These are operating ranges, not quotas.

## Product future

Future customer UX should let the user choose intent such as:
- Quiet
- Normal
- Fast
- Overnight

Courier maps that intent to:
- queue reserve
- admitted motors
- package size
- resource guard

Advanced users may choose logical wall size directly.

The system remains truthful about requested versus admitted versus active capacity.

## Hard invariants

- RESULT_REUSE_FIRST
- NO_BUSYWORK
- NO_EVIDENCE_NO_PASS
- MAX_HEAVY_JOBS follows host policy
- session/provider change does not reset completion
- queue depth does not authorize new architecture
- queue exhaustion does not justify invented work
