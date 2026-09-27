# Courier Adaptive Wall + Universal Device Requirement — 2026-09-27

Status: PRODUCT REQUIREMENT / NEXT-PHASE DESIGN
Does not override the current final-candidate proof path.

## Product promise

Courier must remain useful on weak devices while still scaling up on stronger machines.

A user with an old phone, weak laptop, or low-memory machine must still be able to use Courier meaningfully.

A user with a stronger machine may use a larger wall.

The product must not require a large wall in order to access core product value.

## Core rule

**ALL CORE FUNCTIONS, DIFFERENT LOCAL CONCURRENCY.**

Low-end hardware gets fewer simultaneous local workers, not a crippled product.

Examples:
- weak phone: 1 active logical worker / remote or deferred execution as available
- weak laptop: 1-3 admitted slots
- modest machine: 3-5 admitted slots
- healthy desktop/laptop: 5-10 admitted slots
- stronger host: may admit more when proven safe

These are examples, not fixed hardware promises.

## Requested vs safe admitted wall

The user may request a wall size.

Courier must separately compute:
- REQUESTED
- SAFE_ADMITTED
- ACTIVE
- WAITING
- GUARDED
- RESERVED
- IDLE

The runtime may reduce concurrency without removing product capabilities.

Example:
REQUESTED=10
SAFE_ADMITTED=5
ACTIVE=5
WAITING/GUARDED=5

The remaining work stays queued and continues when capacity becomes available.

## Adaptive device governor

Do not hard-code one wall size per device type.

Measure lightweight runtime signals:
- CPU/load trend
- memory pressure
- swap/pagefile pressure
- recent interaction latency
- owned process count
- provider/API latency
- task queue depth
- thermal signals only where actually available
- recent failure/retry rate

The governor should use conservative hysteresis:
- scale up gradually after sustained healthy operation
- scale down quickly when pressure appears
- avoid oscillating up/down every few seconds

## Smoothness is a product requirement

Courier should protect the user's machine from becoming unusable.

Prefer:
- 4 smooth workers over 8 laggy workers
- 6 smooth workers over 10 unstable workers
- 8 smooth workers over 16 workers that create swap/thermal pressure

The UI should explain:
"Requested 10 · Safe now 6 · 4 waiting"

Never imply the machine is defective simply because Courier admitted fewer slots.

## One-worker mode is first-class

Wall=1 is not a demo mode.

It must support the same core lifecycle:
GOAL -> TASK -> EXECUTION -> RESULT -> VERIFY -> RECONCILE -> NEXT

Work is serialized rather than removed.

This is essential for:
- weak phones
- old laptops
- battery-constrained devices
- accessibility
- users who prefer low resource use

## Feature availability

Core features should not disappear solely because wall size is small.

Keep available:
- goal/task control
- durable ledger
- result/evidence truth
- verification
- restart/recovery
- queue/continue
- cost/resource visibility
- user/owner surface

Only concurrency changes.

Provider-specific or hardware-specific features may still require their real prerequisites.

## Customer wall UX

Beginner surface:
- Wall 1
- Wall 2
- Wall 3
- Wall 4
- Wall 5
- Wall 6
- Wall 7
- Wall 8
- Wall 9
- Wall 10
- AUTO / Recommended

Advanced surface may retain larger exact logical capacities.

AUTO should be the recommended default for ordinary users.

AUTO continuously finds a smooth admitted level instead of maximizing process count.

## Remote/deferred execution

On weak clients, Courier may move eligible work to remote/provider execution when explicitly available and permitted.

The phone/client remains the control surface.

Do not silently spend money or enable remote execution without the applicable user/account permission.

## Aggressiveness rule

Courier is not a benchmark or stress tester.

The scheduler must optimize:
1. useful verified progress
2. responsiveness of the user's device
3. resource safety
4. cost efficiency

Not:
maximum worker count.

## Anti-stampede

When many logical slots are requested:
- stagger starts
- limit simultaneous initialization
- cache/reuse read-only context where safe
- deduplicate identical scans
- prioritize READY work
- keep idle slots near-zero compute

## Current evidence

Observed operator experience shows that large numbers of open AI/CLI windows can cause visible lag on real hardware.

Treat this as product evidence for adaptive admission, not as proof of one universal numeric ceiling.

## Definition of success

A weak device can still complete real Courier work with Wall=1.

A stronger device can smoothly scale upward.

The product remains truthful and responsive at both extremes.

**Capability is universal; concurrency is adaptive.**
