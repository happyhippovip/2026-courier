# Computer-A Autonomy Crash-Safety Acceptance Contract

This reviewer-owned contract defines observable safety outcomes. It does not
prescribe a storage format or implementation strategy.

## A. Idle and endurance

| Precondition | Action | Required persisted evidence | Accept | Reject |
| --- | --- | --- | --- | --- |
| Session has no ready work | Observe more idle cycles than its productive-task limit | Idle/wake state and no fabricated task/result | Productive limit is unchanged; wall-clock is still enforced; new evidence wakes work | Idle consumes productive iterations, spins, or emits unbounded reports |

## B. Execution crash matrix

| Crash point | Required restart result | Forbidden result |
| --- | --- | --- |
| Before durable intent | No claimed execution; safely rediscover or park | A fabricated completion |
| After durable intent, before handler | Resume or reconcile the intent once | Duplicate dispatch |
| During handler / unknown side effect | `RECOVERY_REQUIRED`, `UNKNOWN_EFFECT`, or an equivalent fail-closed state | Blind automatic replay or silent completion |
| After handler, before result persistence | Preserve the uncertain effect and do not re-run it automatically | A second handler effect |
| After persisted result, before completion acknowledgement | Reconcile to one completion | Lost result or repeated execution |
| After completion | Idempotent no-op | A new execution |

## C. Result ingestion

For `receive -> persist -> apply -> acknowledge/dedupe`, a durable dedupe marker
is authoritative only after the authoritative apply step is durable. A restart
must replay an unapplied valid result, while a fully applied duplicate remains
harmless.

## D. Lease reclaim

The stale generation must be removed only if the exact observed generation is
still current. A replacement claim appearing between stale inspection and
cleanup must survive. A stale owner can never release a replacement claim.

## E. Liveness

`RUNNING` without a fresh, identity-bound heartbeat and a matching runtime
owner is not live authority. Restart must choose `STALE`, `PAUSED`,
`RECOVERY_REQUIRED`, or `UNKNOWN`, never falsely live `RUNNING`.

## F. Heavy authority

Two independent processes contending for one heavy provider/scope obtain
exactly one durable authority. The loser is `BUSY`, `DENIED`, or `WAITING`.
Crash recovery must retain the same single-owner rule.

## Anti-cheating conditions

The tests reject counter reset, evidence deletion, exception suppression,
unconditional completion, PID-only liveness, in-memory-only locking, disabling
dedupe, disabling bounds, or treating uncertain effects as success.
