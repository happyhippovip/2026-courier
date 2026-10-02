# L07: TIMEOUT_CROSS_WORKER_FIX_PLAN

## Objective
Implement the Canonical Timeout Law (L06) by aligning L3 (the worker) with L2 (the controller). 

## Exact Fix Packet

### 1. Stop Forging Results for Lost Leases
When the worker's internal time bound for `lease_ttl_s` expires, it must silently abandon the task instead of forging a `RESULT_REJECTED` event. The Controller's watchdog will naturally emit `LEASE_EXPIRED` based on the lack of heartbeats.

**Target File:** `courier_worker/service.py`
**Changes:** Update the early-return block (around line 429) to include `Outcome.LEASE_LOST`.
```python
<<<<
        if result.outcome == Outcome.CANCELLED and not watcher.cancelled():
            # Host shutdown, not a task cancel: the attempt's effect is unknown, so
            # report nothing and let the lease expire.
            adapter_bridge.cleanup(self.home, spec.dispatch_id)
            return "abandoned"
====
        if result.outcome == Outcome.LEASE_LOST or (result.outcome == Outcome.CANCELLED and not watcher.cancelled()):
            # Host shutdown or lease expiration: the attempt's effect is unknown, so
            # report nothing and let the controller's lease expire naturally.
            adapter_bridge.cleanup(self.home, spec.dispatch_id)
            return "abandoned"
>>>>
```

### 2. Timeouts are Deterministic Evidence (`retryable=False`)
When a worker aborts an adapter execution because it exceeded `timeout_s`, it represents a deterministic logic failure (the task was too slow), not a transient infrastructure loss.

**Target File:** `courier_worker/host.py`
**Changes:** Modify the `ExecutionResult.retryable` property to return `False`.
```python
<<<<
    @property
    def retryable(self) -> bool:
        # Only environment-shaped ends are worth a blind retry. A crash or a
        # cancellation is evidence, not a transient: the controller (and the
        # non-idempotent BLOCK rule) must see retryable=false.
        return self.outcome in (Outcome.TIMEOUT, Outcome.LEASE_LOST)
====
    @property
    def retryable(self) -> bool:
        # Executions that exceed timeout_s are deterministic resource failures,
        # not transient environment errors. 
        # LEASE_LOST is handled in service.py via abandonment, but explicitly
        # marked False here to prevent any leakage.
        return False
>>>>
```

## Evidence & Verification
Applying this packet aligns the system so that:
1. `Outcome.TIMEOUT` correctly routes to `RESULT_REJECTED(retryable=False)`.
2. `Outcome.LEASE_LOST` correctly routes to `LEASE_EXPIRED(reason="ttl")` (via L2).
3. Both events correctly funnel into the L02 uncertainty state contract where `Decision.BLOCK` is accurately applied for non-idempotent tasks.
