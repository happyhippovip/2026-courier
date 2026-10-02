# L06: CANONICAL_TIMEOUT_LAW

## The Semantic Divergence
Currently, the worker (L3) treats both `timeout_s` (execution time bound) and `lease_ttl_s` (infrastructure authority bound) as equivalent outcomes (`Outcome.TIMEOUT` and `Outcome.LEASE_LOST`). It bundles both into a `RESULT_REJECTED` with `retryable=True`. 
Simultaneously, the controller (L2) watchdog emits `LEASE_EXPIRED` when it hasn't heard a heartbeat within `lease_ttl_s`.
This causes a race condition where the same physical event (running out of time) is recorded differently depending on which boundary writes it first, confusing downstream idempotency rules.

## The Canonical Law

**1. TIMEOUT is a Deterministic Execution Failure (L3 Authority)**
When an execution exceeds `timeout_s`, it has deterministically failed its resource budget (e.g., a slow query, a hanging adapter). 
* **Worker Action:** Emit `RESULT_REJECTED(retryable=False)`. It is NOT a transient infrastructure error. Retrying a deterministically slow task blindly wastes resources.

**2. LEASE_LOST is an Authority / Infrastructure Loss (L2 Authority)**
When wall-clock time exceeds `lease_ttl_s`, the worker has lost its authority to act on behalf of the controller.
* **Worker Action:** The worker MUST drop the task and exit immediately. It MUST NOT emit `RESULT_READY` or `RESULT_REJECTED`. 
* **Controller Action:** The L2 Watchdog durably emits `LEASE_EXPIRED(reason="ttl")`, which invokes the correct uncertainty and idempotency protections in the state machine.

## Conclusion
By enforcing this canonical law, we strictly partition responsibilities: L3 owns deterministic execution bounds (Timeouts) and explicitly rejects them, while L2 owns authority/infrastructure bounds (Leases) and records them as uncertainty events.
