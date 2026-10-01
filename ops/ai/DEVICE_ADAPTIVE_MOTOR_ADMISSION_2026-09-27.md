# Courier Symphony — Device-Adaptive Motor Admission — 2026-09-27

Status: PRODUCT/OPERATIONS REQUIREMENT  
Authority: complements wall scaling; does not override the current final-candidate proof path.

## Problem

A large logical wall does not mean a device can run the same number of active workers smoothly.

Real hosts differ. One machine may stay smooth with 10 active lightweight workers while another may only sustain 4, 5, 6, 8 or 9.

Courier must not assume that a requested wall size is the safe active motor count.

## Core distinction

Persist and display separately:

- REQUESTED_WALL_SLOTS
- ADMITTED_MOTORS
- ACTIVE_MOTORS
- WAITING_SLOTS
- GUARDED_SLOTS
- RESERVED_INTERACTIVE
- HEAVY_JOBS
- THROTTLE_REASON

The user's wall size is a desired logical capacity.

The admitted motor count is the safe current concurrency for this specific host.

## Product rule

**Smooth useful work beats maximum concurrency.**

Examples:

- Requested 10 / Admitted 10 / Active 9 / Waiting 1
- Requested 10 / Admitted 6 / Active 6 / Guarded 4
- Requested 8 / Admitted 5 / Active 5 / Guarded 3

Never imply that all requested slots are active when the host cannot sustain them.

## Device calibration

Courier should learn a per-device operating envelope instead of using one global fixed number.

Initial calibration should be lightweight and reversible.

Suggested behavior:

1. start with a conservative active-motor count;
2. observe responsiveness and resource trends;
3. increase one motor at a time;
4. wait for a stabilization window;
5. stop increasing when latency/resource pressure materially worsens;
6. back off by at least one motor;
7. keep the stable value as the current admitted ceiling;
8. re-evaluate later if workload type or host conditions change.

Do not run synthetic stress merely to discover the maximum.

Use normal useful work as the calibration workload when possible.

## Signals

Admission may consider lightweight signals such as:

- CPU/load trend
- RAM pressure
- swap/pagefile growth
- owned process count
- application/terminal responsiveness
- provider/API latency
- repeated tool timeout/hang signals
- thermal pressure when actually measurable
- task completion latency
- user-visible lag
- host-specific historical stable ceiling

No single signal is sufficient by itself.

## Hysteresis / anti-flapping

Do not oscillate rapidly between motor counts.

Use separate thresholds for scale-up and scale-down.

Example behavior:

- scale down quickly on sustained pressure;
- scale up slowly after a meaningful stable interval.

## Workload classes

Motor capacity depends on work type.

Track at least:

- LIGHT_READ_ONLY
- TARGETED_TEST
- HEAVY_JOB
- PHYSICAL_RUNTIME

A host may safely run many LIGHT_READ_ONLY motors while still allowing only:

MAX_HEAVY_JOBS=1

unless a later proven policy explicitly changes that.

## Customer UX

For normal customers, Courier should make wall selection simple while handling admission automatically.

Example:

User selects WALL 10.

Courier may show:

Wall requested: 10
Safe now: 6
Working: 6
Guarded: 4
Reason: memory/pagefile pressure

The user should not need to understand process counts or manually tune every machine.

## Beginner wall

Starter/customer-facing wall options may emphasize 1..10.

Advanced mode may retain exact logical wall values beyond 10 as defined by the broader wall requirements.

The active motor count remains device-adaptive in both modes.

## Per-device persistence

Courier should persist a lightweight host profile containing:

- host identity/fingerprint that does not expose unnecessary personal data
- last known stable admitted motor count
- last pressure reason
- recent workload class
- last calibration timestamp
- observed stable range

Do not treat yesterday's value as permanent truth.

## Overnight behavior

Before unattended work:

1. begin at last known safe admitted ceiling or a conservative fallback;
2. reserve interactive capacity if requested;
3. observe early-session stability;
4. reduce admitted motors immediately if the host degrades;
5. never open more work merely to keep every logical slot visibly busy.

## Important non-goal

This requirement is not permission to spawn 64 or 100 resident processes.

Logical wall capacity may be large while active motors remain much smaller.

## Current observation

Current operator experience indicates that smooth active concurrency may vary materially by device, with practical values such as 4, 5, 6, 8, 9 or 10 depending on the host and current workload.

This is observational input, not yet a benchmark.

A forthcoming video may provide additional evidence for tuning this policy.

## Implementation order

Do not derail the current core proof path.

After final candidate / RUN_1 / RUN_2 proof, implement:

1. truthful requested-vs-admitted-vs-active state
2. per-device motor admission
3. pressure backoff
4. slow scale-up
5. persisted host profile
6. customer-facing simple wall selector
7. later automatic calibration refinement
